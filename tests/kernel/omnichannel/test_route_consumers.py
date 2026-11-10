"""OMNI-014.2: reuse RKJO AgentMessage/EventBus and operator inbox tenant isolation."""
import os
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from rkjo_kernel.omnichannel.conversation_router import RoutedInbound
from rkjo_kernel.omnichannel.inbound import InboundKind, VerifiedInbound
from rkjo_kernel.omnichannel.route_consumers import (
    RKJOAgentRouteConsumer, PostgreSQLOperatorInbox, route_id,
)


def pair(destination="agent", *, tenant="tenant-a"):
    route = RoutedInbound(
        tenant_id=tenant, channel="whatsapp",channel_account_id="phone-a",
        provider_event_id="m1", conversation_id="conversation-1",
        destination=destination, ownership_version=1,
    )
    event = VerifiedInbound(
        tenant_id=tenant,channel="whatsapp",channel_account_id="phone-a",
        provider_event_id="m1",kind=InboundKind.USER_MESSAGE,
        payload={"event":{"id":"m1","from":"customer-a","text":{"body":"Hello"}}},
    )
    return route,event


class Bus:
    def __init__(self):
        self.published = []
    def publish_agent_message(self, *, queue_name, message):
        self.published.append((queue_name,message))


@pytest.fixture
def inbox():
    url = os.getenv("RKJO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("RKJO_TEST_DATABASE_URL required.")
    if "test" not in conninfo_to_dict(url).get("dbname", "").lower():
        pytest.fail("Use a dedicated test DB.")
    schema = "rkjo_omni_operator_" + uuid4().hex
    with psycopg.connect(url) as conn:
        conn.execute('CREATE SCHEMA "' + schema + '"')
    scoped = make_conninfo(url, options="-c search_path=" + schema)
    try:
        store = PostgreSQLOperatorInbox(scoped)
        store.initialize_schema()
        yield store
    finally:
        with psycopg.connect(url) as conn:
            conn.execute('DROP SCHEMA "' + schema + '" CASCADE')


def test_agent_adapter_uses_existing_eventbus_and_stable_message_id():
    bus = Bus()
    adapter = RKJOAgentRouteConsumer(bus=bus,agent_name="rkjo.agent",queue_name="rkjo.agent.queue")
    route,event = pair()
    adapter.deliver(route=route,event=event)
    adapter.deliver(route=route,event=event)
    assert len(bus.published) == 2
    assert all(queue == "rkjo.agent.queue" for queue,_ in bus.published)
    first = bus.published[0][1]
    assert first.message_id == bus.published[1][1].message_id
    assert first.target == "rkjo.agent"
    assert first.metadata["tenant_id"] == "tenant-a"
    assert first.metadata["ownership_version"] == 1
    assert first.payload["conversation_id"] == "conversation-1"


def test_agent_adapter_rejects_spoofed_tenant_and_wrong_destination():
    bus = Bus()
    adapter = RKJOAgentRouteConsumer(bus=bus,agent_name="rkjo.agent",queue_name="rkjo.queue")
    route,event = pair()
    with pytest.raises(PermissionError):
        adapter.deliver(route=route,event=pair(tenant="tenant-b")[1])
    with pytest.raises(ValueError):
        adapter.deliver(route=pair("human")[0],event=event)
    assert bus.published == []


def test_operator_inbox_idempotent_and_tenant_filtered(inbox):
    route,event = pair("human")
    inbox.deliver(route=route,event=event)
    inbox.deliver(route=route,event=event)
    rows = inbox.list_conversation(tenant_id="tenant-a",conversation_id="conversation-1")
    assert len(rows) == 1
    assert rows[0].route_id == route_id(route)
    assert rows[0].event_payload["event"]["text"]["body"] == "Hello"
    assert inbox.list_conversation(tenant_id="tenant-b",conversation_id="conversation-1") == []


def test_operator_inbox_rejects_agent_routes_and_tenant_spoofing(inbox):
    route,event = pair("human")
    with pytest.raises(ValueError):
        inbox.deliver(route=pair("agent")[0],event=event)
    with pytest.raises(PermissionError):
        inbox.deliver(route=route,event=pair(tenant="tenant-b")[1])
    assert inbox.list_conversation(tenant_id="tenant-a",conversation_id="conversation-1") == []


def test_operator_inbox_detects_same_id_different_payload(inbox):
    route,event = pair("human")
    inbox.deliver(route=route,event=event)
    altered = VerifiedInbound(
        tenant_id=event.tenant_id,channel=event.channel,
        channel_account_id=event.channel_account_id,
        provider_event_id=event.provider_event_id,
        kind=event.kind,payload={"event":{"id":"m1","text":{"body":"changed"}}},
    )
    with pytest.raises(ValueError,match="collision"):
        inbox.deliver(route=route,event=altered)
    assert inbox.list_conversation(tenant_id="tenant-a",conversation_id="conversation-1")[0].event_payload == dict(event.payload)


def test_route_id_isolation_across_tenants_and_accounts():
    first,_ = pair()
    other,_ = pair(tenant="tenant-b")
    assert route_id(first) != route_id(other)
    assert route_id(first) != route_id(RoutedInbound(
        tenant_id=first.tenant_id,channel=first.channel,
        channel_account_id="different-phone",provider_event_id=first.provider_event_id,
        conversation_id=first.conversation_id,destination=first.destination,
        ownership_version=first.ownership_version,
    ))
