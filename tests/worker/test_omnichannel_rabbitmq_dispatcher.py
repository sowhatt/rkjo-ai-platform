"""OMNI-016.1: outbox -> RKJO EventBus transport integration.

These use the actual PostgreSQL outbox and a deterministic bus double.
Broker-level confirms/ACK/NACK/DLQ are exercised by RKJO's existing
tests/kernel/test_rabbitmq_* suite. An opt-in broker smoke test follows.
"""
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from rkjo_kernel.omnichannel.conversation_router import PostgreSQLConversationRouter
from rkjo_kernel.omnichannel.route_consumers import PostgreSQLOperatorInbox
from rkjo_kernel.omnichannel.inbound import InboundKind, VerifiedInbound
from rkjo_worker.omnichannel_dispatcher import RabbitMQOmnichannelDispatcher


NOW = datetime.now(timezone.utc)


class Bus:
    def __init__(self, *, fail=False):
        self.messages = []
        self.fail = fail
        self.closed = False

    def publish_agent_message(self, *, queue_name, message):
        if self.fail:
            raise ConnectionError("SimulatedRabbitMQConfirmFailure")
        self.messages.append((queue_name, message))

    def close(self):
        self.closed = True


def inbound(ident="msg-1"):
    return VerifiedInbound(
        tenant_id="tenant-a", channel="whatsapp",
        channel_account_id="phone-a", provider_event_id=ident,
        kind=InboundKind.USER_MESSAGE,
        payload={"event": {"id":ident, "from":"contact-a",
                           "timestamp":"1700000001", "text":{"body":"Hello"}}},
    )


@pytest.fixture
def stack():
    database_url = os.environ.get("RKJO_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("RKJO_TEST_DATABASE_URL required")
    if "test" not in conninfo_to_dict(database_url).get("dbname","").lower():
        pytest.fail("Dedicated test DB required")
    schema = "rkjo_omni_rabbit_" + uuid4().hex
    with psycopg.connect(database_url) as conn:
        conn.execute('CREATE SCHEMA "' + schema + '"')
    scoped = make_conninfo(database_url, options="-c search_path=" + schema)
    try:
        router = PostgreSQLConversationRouter(scoped)
        router.initialize_schema()
        PostgreSQLOperatorInbox(scoped).initialize_schema()
        yield scoped, router
    finally:
        with psycopg.connect(database_url) as conn:
            conn.execute('DROP SCHEMA "' + schema + '" CASCADE')


def dispatcher(url, bus, **kwargs):
    return RabbitMQOmnichannelDispatcher(
        database_url=url, bus_factory=lambda:bus,
        agent_name="rkjo.omni.agent",
        queue_name="rkjo.omnichannel.agent.test",
        **kwargs,
    )


def test_confirmed_publish_marks_outbox_processed(stack):
    url, router = stack
    router.route(inbound())
    bus = Bus()
    assert dispatcher(url,bus).dispatch_batch(now=NOW) == 1
    assert bus.closed
    assert len(bus.messages) == 1
    queue,msg = bus.messages[0]
    assert queue == "rkjo.omnichannel.agent.test"
    assert msg.metadata["tenant_id"] == "tenant-a"
    assert msg.message_type == "omnichannel.inbound.message"
    assert dispatcher(url,Bus()).dispatch_batch(now=NOW) == 0
    with psycopg.connect(url) as conn:
        assert conn.execute("SELECT status FROM omni_route_outbox").fetchone()[0] == "processed"


def test_broker_confirmation_failure_keeps_route_retryable(stack):
    url, router = stack
    router.route(inbound())
    failed_bus = Bus(fail=True)
    assert dispatcher(url,failed_bus).dispatch_batch(now=NOW) == 1
    assert failed_bus.closed
    with psycopg.connect(url) as conn:
        status,error=conn.execute(
            "SELECT status,last_error FROM omni_route_outbox"
        ).fetchone()
    assert (status,error)==("pending","ConnectionError")
    success = Bus()
    assert dispatcher(url,success).dispatch_batch(now=NOW+timedelta(seconds=6)) == 1
    assert len(success.messages)==1


def test_replay_after_publish_uses_identical_message_id(stack):
    url,router = stack
    router.route(inbound())
    from rkjo_kernel.omnichannel.route_outbox import PostgreSQLRouteOutbox
    from rkjo_kernel.omnichannel.route_consumers import RKJOAgentRouteConsumer
    outbox=PostgreSQLRouteOutbox(url)
    claim=outbox.claim_due(now=NOW,lease_seconds=2)
    bus=Bus()
    RKJOAgentRouteConsumer(bus=bus,agent_name="rkjo.omni.agent",
                           queue_name="rkjo.omnichannel.agent.test").deliver(
                               route=claim.route,event=claim.event,
                           )
    # Broker accepted publication, process stopped before outbox ACK.
    assert dispatcher(url,bus).dispatch_batch(now=NOW+timedelta(seconds=3)) == 1
    assert len(bus.messages)==2
    assert bus.messages[0][1].message_id == bus.messages[1][1].message_id


def test_human_route_does_not_publish_to_rabbitmq(stack):
    url,router=stack
    route=router.route(inbound())
    router.transfer(tenant_id="tenant-a",conversation_id=route.conversation_id,
                    expected_version=0,operator_id="operator-a")
    router.route(inbound("msg-2"))
    bus=Bus()
    assert dispatcher(url,bus).dispatch_batch(now=NOW) == 2
    assert bus.messages==[]
    with psycopg.connect(url) as conn:
        assert conn.execute("SELECT count(*) FROM omni_operator_inbox").fetchone()[0]==1


def test_invalid_configuration_and_clock(stack):
    url,_=stack
    with pytest.raises(ValueError):
        dispatcher(url,Bus(),lease_seconds=0)
    with pytest.raises(ValueError):
        dispatcher(url,Bus()).dispatch_batch(now=NOW.replace(tzinfo=None))
