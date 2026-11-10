"""OMNI-015.2: real-PostgreSQL crash/replay/concurrency fault-injection tests.

No external provider is contacted. Duplicate EventBus publications after a
crash are possible with at-least-once dispatch; the stable AgentMessage ID is
what a downstream idempotent consumer MUST use.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from rkjo_kernel.omnichannel.conversation_router import PostgreSQLConversationRouter
from rkjo_kernel.omnichannel.inbound import InboundKind, VerifiedInbound
from rkjo_kernel.omnichannel.inbound_processor import (
    InboundProcessingWorker, PostgreSQLInboundProcessorStore,
)
from rkjo_kernel.omnichannel.postgres_inbox import PostgreSQLInboundInbox
from rkjo_kernel.omnichannel.route_consumers import (
    RKJOAgentRouteConsumer, PostgreSQLOperatorInbox,
)
from rkjo_kernel.omnichannel.route_outbox import (
    PostgreSQLRouteOutbox, RoutingDispatchWorker,
)

NOW = datetime.now(timezone.utc)


class Bus:
    def __init__(self):
        self.published = []

    def publish_agent_message(self, queue_name, message):
        self.published.append((queue_name, message))


def event(name="m1"):
    return VerifiedInbound(
        tenant_id="tenant-a", channel="whatsapp",
        channel_account_id="phone-a", provider_event_id=name,
        kind=InboundKind.USER_MESSAGE,
        payload={"event": {"id": name, "from": "customer-a",
                           "timestamp": "1700000001", "text": {"body": "hello"}}},
    )


@pytest.fixture
def db():
    url = os.getenv("RKJO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("RKJO_TEST_DATABASE_URL required.")
    if "test" not in conninfo_to_dict(url).get("dbname", "").lower():
        pytest.fail("Dedicated PostgreSQL test database required.")
    schema = "rkjo_omni_fault_" + uuid4().hex
    with psycopg.connect(url) as conn:
        conn.execute('CREATE SCHEMA "' + schema + '"')
    scoped = make_conninfo(url, options="-c search_path=" + schema)
    try:
        inbox = PostgreSQLInboundInbox(scoped)
        inbox.initialize_schema()
        inbound = PostgreSQLInboundProcessorStore(scoped, max_attempts=3)
        inbound.initialize_schema()
        router = PostgreSQLConversationRouter(scoped)
        router.initialize_schema()
        outbox = PostgreSQLRouteOutbox(scoped, max_attempts=3)
        operators = PostgreSQLOperatorInbox(scoped)
        operators.initialize_schema()
        yield scoped, inbox, inbound, router, outbox, operators
    finally:
        with psycopg.connect(url) as conn:
            conn.execute('DROP SCHEMA "' + schema + '" CASCADE')


def test_concurrent_outbox_workers_cannot_claim_same_route(db):
    _,_,_,router,outbox,_ = db
    route = router.route(event())
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(
            lambda _: outbox.claim_due(now=NOW, lease_seconds=30),
            range(2),
        ))
    assert sum(c is not None for c in claims) == 1
    outbox.finish(next(c for c in claims if c is not None))
    assert outbox.claim_due(now=NOW) is None


def test_crash_after_bus_publish_before_ack_replays_same_identity(db):
    _,_,_,router,outbox,operator = db
    router.route(event())
    bus = Bus()
    agent = RKJOAgentRouteConsumer(
        bus=bus, agent_name="rkjo.agent", queue_name="rkjo.agent.queue",
    )
    first = outbox.claim_due(now=NOW, lease_seconds=2)
    assert first is not None
    agent.deliver(route=first.route, event=first.event)
    # Simulated process crash: no finish() after bus accepted publication.
    second = outbox.claim_due(now=NOW+timedelta(seconds=3), lease_seconds=2)
    assert second is not None
    agent.deliver(route=second.route, event=second.event)
    outbox.finish(second)
    assert len(bus.published) == 2
    assert bus.published[0][1].message_id == bus.published[1][1].message_id
    assert bus.published[0][1].metadata["route_id"] == bus.published[1][1].metadata["route_id"]
    with pytest.raises(ValueError, match="Stale"):
        outbox.finish(first)
    assert outbox.claim_due(now=NOW+timedelta(seconds=6)) is None


def test_inbound_crash_after_route_commit_retries_without_second_outbox(db):
    url,inbox,inbound,router,outbox,_ = db
    assert inbox.accept_once(event())
    first = inbound.claim_due(now=NOW,lease_seconds=2)
    assert first is not None
    route = router.route(first.event)
    # Crash between transactionally committed route and inbound ACK.
    again = inbound.claim_due(now=NOW+timedelta(seconds=3),lease_seconds=2)
    assert again is not None
    assert router.route(again.event) == route
    inbound.mark_processed(again)
    with pytest.raises(ValueError,match="Stale"):
        inbound.mark_processed(first)
    with psycopg.connect(url) as conn:
        assert conn.execute("SELECT count(*) FROM omni_routed_inbound").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM omni_route_outbox").fetchone()[0] == 1


def test_operator_retry_after_db_commit_does_not_duplicate(db):
    _,_,_,router,outbox,operator = db
    initial = router.route(event())
    router.transfer(
        tenant_id="tenant-a",conversation_id=initial.conversation_id,
        expected_version=0,operator_id="operator-a",
    )
    # Old agent response was queued before takeover; it is no longer eligible.
    claim_old = outbox.claim_due(now=NOW)
    assert claim_old is not None
    outbox.finish(claim_old, obsolete=True)
    route = router.route(event("m2"))
    assert route.destination == "human"
    claim = outbox.claim_due(now=NOW)
    assert claim is not None and claim.route == route
    operator.deliver(route=claim.route, event=claim.event)
    # Crash before finishing the route, then consume it again.
    claim_replayed = outbox.claim_due(now=NOW + timedelta(seconds=31))
    assert claim_replayed is not None
    operator.deliver(route=claim_replayed.route, event=claim_replayed.event)
    outbox.finish(claim_replayed)
    assert len(operator.list_conversation(
        tenant_id="tenant-a",conversation_id=route.conversation_id,
    )) == 1


def test_exhausted_crash_lease_not_claimed_again(db):
    url,_,_,router,outbox,_ = db
    router.route(event())
    for attempt in range(3):
        claim = outbox.claim_due(
            now=NOW+timedelta(seconds=attempt*3), lease_seconds=2,
        )
        assert claim is not None and claim.attempt == attempt+1
    assert outbox.claim_due(now=NOW+timedelta(seconds=10)) is None
    with psycopg.connect(url) as conn:
        assert conn.execute(
            "SELECT status FROM omni_route_outbox"
        ).fetchone()[0] == "failed"
