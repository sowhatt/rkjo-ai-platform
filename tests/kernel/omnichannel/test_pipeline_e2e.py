"""OMNI-015.1 end-to-end verification of authenticated WhatsApp ingress.

PostgreSQL is real and isolated. The Meta HTTP client / RKJO EventBus are
test doubles: this verifies wiring, not production provider availability.
"""
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from rkjo_kernel.omnichannel.inbound import InboundRoute
from rkjo_kernel.omnichannel.pipeline import build_pipeline
from rkjo_kernel.omnichannel.provider_security import (
    ProviderAccount, ProviderWebhookVerifier, StaticProviderAccountRegistry,
)
from rkjo_kernel.omnichannel.route_consumers import RKJOAgentRouteConsumer


NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
SECRET = "test-meta-app-secret"


class Bus:
    def __init__(self):
        self.messages = []

    def publish_agent_message(self, queue_name, message):
        self.messages.append((queue_name, message))


def signed(event, *, kind="messages", account="phone-a", secret=SECRET):
    body = json.dumps({"entry": [{"changes": [{"value": {
        "metadata": {"phone_number_id": account}, kind: [event],
    }}]}]}, separators=(",", ":")).encode()
    headers = {
        "x-hub-signature-256": "sha256=" + hmac.new(
            secret.encode(), body, hashlib.sha256,
        ).hexdigest(),
    }
    return body, headers


@pytest.fixture
def setup():
    url = os.environ.get("RKJO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("RKJO_TEST_DATABASE_URL required")
    if "test" not in conninfo_to_dict(url).get("dbname", "").lower():
        pytest.fail("Use dedicated test database")
    schema = "rkjo_omni_pipeline_" + uuid4().hex
    with psycopg.connect(url) as conn:
        conn.execute('CREATE SCHEMA "' + schema + '"')
    scoped = make_conninfo(url, options="-c search_path=" + schema)
    try:
        registry = StaticProviderAccountRegistry([
            ProviderAccount(
                channel="whatsapp", channel_account_id="phone-a",
                tenant_id="tenant-a", credential=SECRET,
            ),
        ])
        bus = Bus()
        pipeline = build_pipeline(
            database_url=scoped,
            verifier=ProviderWebhookVerifier(accounts=registry),
            agent=RKJOAgentRouteConsumer(
                bus=bus,agent_name="rkjo.assistant",queue_name="rkjo.agent.queue",
            ),
        )
        yield pipeline, bus, scoped
    finally:
        with psycopg.connect(url) as conn:
            conn.execute('DROP SCHEMA "' + schema + '" CASCADE')


def inbound(message_id="in-1"):
    return signed({
        "id": message_id, "from": "customer-1",
        "timestamp": "1791630000", "text": {"body": "Hello RKJO"},
    })


def receipt():
    return signed({
        "id": "wamid-provider-1", "status": "delivered",
        "timestamp": "1791630001",
    },kind="statuses")


def test_signed_message_routes_into_existing_agent_bus_once(setup):
    pipeline, bus, url = setup
    body, headers = inbound()
    assert pipeline.gateway.receive(channel="whatsapp",body=body,headers=headers) == InboundRoute.PENDING_MESSAGE
    assert pipeline.drain(now=NOW) == (1, 1)
    assert len(bus.messages) == 1
    queue, message = bus.messages[0]
    assert queue == "rkjo.agent.queue"
    assert message.metadata["tenant_id"] == "tenant-a"
    assert message.message_type == "omnichannel.inbound.message"
    assert pipeline.gateway.receive(channel="whatsapp",body=body,headers=headers) == InboundRoute.DUPLICATE
    assert pipeline.drain(now=NOW) == (0, 0)
    assert len(bus.messages) == 1


def test_agent_routing_human_takeover_then_operator_inbox(setup):
    pipeline,bus,url = setup
    body,headers = inbound()
    pipeline.gateway.receive(channel="whatsapp",body=body,headers=headers)
    assert pipeline.drain(now=NOW) == (1,1)
    with psycopg.connect(url) as conn:
        row = conn.execute("""
            SELECT conversation_id,ownership_version FROM omni_conversations
            WHERE tenant_id='tenant-a'
        """).fetchone()
    conversation,version = row
    pipeline.conversations.transfer(
        tenant_id="tenant-a",conversation_id=conversation,
        expected_version=version,operator_id="operator-1",
    )
    b2,h2=inbound("in-2")
    pipeline.gateway.receive(channel="whatsapp",body=b2,headers=h2)
    assert pipeline.drain(now=NOW) == (1,1)
    assert len(bus.messages) == 1
    items = pipeline.operators.list_conversation(
        tenant_id="tenant-a",conversation_id=conversation,
    )
    assert len(items) == 1
    assert items[0].ownership_version == version + 1
    assert pipeline.operators.list_conversation(
        tenant_id="tenant-b",conversation_id=conversation,
    ) == []


def test_signed_receipt_updates_delivery_without_agent_invocation(setup):
    pipeline,bus,url = setup
    pipeline.delivery.register_sent(
        tenant_id="tenant-a", notification_id="notify-1",
        channel="whatsapp",channel_account_id="phone-a",
        provider_message_id="wamid-provider-1",
    )
    body,headers = receipt()
    assert pipeline.gateway.receive(
        channel="whatsapp",body=body,headers=headers,
    ) == InboundRoute.PENDING_RECEIPT
    assert pipeline.drain(now=NOW) == (1, 0)
    state = pipeline.delivery.load(tenant_id="tenant-a",notification_id="notify-1")
    assert state.status.value == "delivered"
    assert bus.messages == []
    assert pipeline.gateway.receive(
        channel="whatsapp",body=body,headers=headers,
    ) == InboundRoute.DUPLICATE


def test_invalid_signature_never_reaches_inbox(setup):
    pipeline,bus,url = setup
    body,headers = inbound()
    headers["x-hub-signature-256"] = "sha256=" + "0"*64
    with pytest.raises(PermissionError):
        pipeline.gateway.receive(channel="whatsapp",body=body,headers=headers)
    with psycopg.connect(url) as conn:
        assert conn.execute("SELECT count(*) FROM omni_inbound_events").fetchone()[0] == 0
    assert pipeline.drain(now=NOW) == (0,0)
