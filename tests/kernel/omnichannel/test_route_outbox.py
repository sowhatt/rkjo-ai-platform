"""OMNI-014.1 transactional route outbox and ownership version fencing."""
from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from rkjo_kernel.omnichannel.conversation_router import PostgreSQLConversationRouter, ConversationRoutingHandler
from rkjo_kernel.omnichannel.inbound import InboundKind, VerifiedInbound
from rkjo_kernel.omnichannel.route_outbox import PostgreSQLRouteOutbox, RoutingDispatchWorker


NOW = datetime.now(timezone.utc)


@pytest.fixture
def stack():
    url = os.getenv("RKJO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("RKJO_TEST_DATABASE_URL required.")
    if "test" not in conninfo_to_dict(url).get("dbname", "").lower():
        pytest.fail("Dedicated test DB required.")
    schema = "rkjo_omni_outbox_" + uuid4().hex
    with psycopg.connect(url) as conn:
        conn.execute('CREATE SCHEMA "' + schema + '"')
    scoped = make_conninfo(url, options="-c search_path=" + schema)
    try:
        router = PostgreSQLConversationRouter(scoped)
        router.initialize_schema()
        outbox = PostgreSQLRouteOutbox(scoped, max_attempts=3)
        yield router, outbox, scoped
    finally:
        with psycopg.connect(url) as conn:
            conn.execute('DROP SCHEMA "' + schema + '" CASCADE')


def incoming(ident="m1", *, account="phone-1"):
    return VerifiedInbound(
        tenant_id="tenant-a",channel="whatsapp",
        channel_account_id=account,provider_event_id=ident,
        kind=InboundKind.USER_MESSAGE,
        payload={"event":{"from":"customer-1","timestamp":"1700000001",
                          "id":ident,"text":{"body":"hello"}}},
    )


class Sink:
    def __init__(self, fail=False):
        self.items = []
        self.fail = fail
    def deliver(self, *, route, event):
        if self.fail:
            raise RuntimeError("SimulatedConsumerFailure")
        self.items.append((route,event))


def test_one_routing_decision_has_one_outbox_event_even_after_replay(stack):
    router,outbox,url = stack
    first = router.route(incoming())
    assert router.route(incoming()) == first
    with psycopg.connect(url) as conn:
        count = conn.execute("SELECT COUNT(*) FROM omni_route_outbox").fetchone()[0]
    assert count == 1
    claim = outbox.claim_due(now=NOW)
    assert claim.route == first
    assert claim.event.payload["event"]["text"]["body"] == "hello"
    outbox.finish(claim)
    assert outbox.claim_due(now=NOW) is None


def test_agent_dispatch_and_stale_human_handoff_fence(stack):
    router,outbox,_ = stack
    agent,operator = Sink(),Sink()
    first = router.route(incoming())
    router.transfer(tenant_id=first.tenant_id,conversation_id=first.conversation_id,
                    expected_version=0,operator_id="operator-1")
    worker = RoutingDispatchWorker(store=outbox,conversations=router,
                                   agent=agent,operator=operator)
    assert worker.run_once(now=NOW)
    assert agent.items == []
    assert operator.items == []
    second = router.route(incoming("m2"))
    assert second.destination == "human"
    assert worker.run_once(now=NOW)
    assert len(operator.items) == 1
    assert operator.items[0][0] == second
    assert not worker.run_once(now=NOW)


def test_routing_consumer_failure_retries_after_delay(stack):
    router,outbox,_ = stack
    router.route(incoming())
    agent = Sink(fail=True)
    worker = RoutingDispatchWorker(store=outbox,conversations=router,
                                   agent=agent,operator=Sink())
    assert worker.run_once(now=NOW)
    assert not worker.run_once(now=NOW + timedelta(seconds=2))
    agent.fail = False
    assert worker.run_once(now=NOW + timedelta(seconds=6))
    assert len(agent.items) == 1
    assert not worker.run_once(now=NOW + timedelta(seconds=6))


def test_crash_expired_lease_and_stale_ack(stack):
    router,outbox,_ = stack
    router.route(incoming())
    first = outbox.claim_due(now=NOW,lease_seconds=2)
    assert outbox.claim_due(now=NOW + timedelta(seconds=1)) is None
    second = outbox.claim_due(now=NOW + timedelta(seconds=3))
    assert second.route == first.route
    assert second.attempt == 2
    with pytest.raises(ValueError,match="Stale"):
        outbox.finish(first)
    outbox.finish(second)


def test_failed_consumer_exhausts_attempt_budget(stack):
    router,outbox,_ = stack
    router.route(incoming())
    worker = RoutingDispatchWorker(store=outbox,conversations=router,
                                   agent=Sink(fail=True),operator=Sink())
    for i in range(3):
        assert worker.run_once(now=NOW + timedelta(seconds=i*10))
    assert not worker.run_once(now=NOW + timedelta(seconds=40))


def test_replay_different_payload_is_rejected(stack):
    router,outbox,_ = stack
    router.route(incoming())
    altered = VerifiedInbound(
        tenant_id="tenant-a",channel="whatsapp",channel_account_id="phone-1",
        provider_event_id="m1",kind=InboundKind.USER_MESSAGE,
        payload={"event":{"from":"customer-1","timestamp":"1700000001",
                          "id":"m1","text":{"body":"changed"}}},
    )
    with pytest.raises(ValueError,match="Conflicting durable"):
        router.route(altered)


def test_receipt_cannot_enter_agent_operator_outbox(stack):
    router,outbox,_ = stack
    receipt = VerifiedInbound(
        tenant_id="tenant-a",channel="whatsapp",channel_account_id="phone-1",
        provider_event_id="status:x:sent:1700000001",
        kind=InboundKind.DELIVERY_RECEIPT,
        payload={"event":{"from":"customer-1","timestamp":"1700000001"}},
    )
    with pytest.raises(ValueError,match="Only user messages"):
        ConversationRoutingHandler(router).handle(receipt)
    assert outbox.claim_due(now=NOW) is None
