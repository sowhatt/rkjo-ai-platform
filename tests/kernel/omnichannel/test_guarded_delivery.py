"""OMNI-014.3 integration tests against isolated PostgreSQL conversation state."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event
import os
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.multimodal.notifications import Notification, NotificationStatus
from rkjo_kernel.omnichannel.conversation_router import PostgreSQLConversationRouter
from rkjo_kernel.omnichannel.contracts import ChannelResponse, ResponseKind, ResponseOrigin
from rkjo_kernel.omnichannel.guarded_delivery import (
    OwnershipFencedChannelAdapter, ObsoleteConversationResponse,
)
from rkjo_kernel.omnichannel.inbound import InboundKind, VerifiedInbound


class Policy:
    def __init__(self, denied=False):
        self.denied = denied
        self.calls = 0

    def check(self, response):
        self.calls += 1
        if self.denied:
            raise PermissionError("Channel policy rejected.")


class Sender:
    def __init__(self, *, entered=None, release=None):
        self.calls = []
        self.entered = entered
        self.release = release

    def send(self, *, notification, message):
        self.calls.append((notification, message))
        if self.entered is not None:
            self.entered.set()
        if self.release is not None:
            assert self.release.wait(timeout=5), "Timed out waiting for provider release"
        return "provider-out-1"


@pytest.fixture
def context():
    url = os.getenv("RKJO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires RKJO_TEST_DATABASE_URL.")
    if "test" not in conninfo_to_dict(url).get("dbname", "").lower():
        pytest.fail("Dedicated test database required.")
    schema = "rkjo_omni_send_" + uuid4().hex
    with psycopg.connect(url) as conn:
        conn.execute('CREATE SCHEMA "' + schema + '"')
    scoped = make_conninfo(url, options="-c search_path=" + schema)
    try:
        router = PostgreSQLConversationRouter(scoped)
        router.initialize_schema()
        event = VerifiedInbound(
            tenant_id="tenant-a", channel="whatsapp",
            channel_account_id="phone-a",provider_event_id="m1",
            kind=InboundKind.USER_MESSAGE,
            payload={"event":{"id":"m1","from":"recipient-1","timestamp":"1700000001"}},
        )
        route = router.route(event)
        yield scoped,router,route
    finally:
        with psycopg.connect(url) as conn:
            conn.execute('DROP SCHEMA "' + schema + '" CASCADE')


def build(route, *, origin="agent", version=0, account="phone-a",
          tenant="tenant-a", operator_id=None):
    response = ChannelResponse(
        notification_id="notify-1", tenant_id=tenant,
        conversation_id=route.conversation_id,
        channel="whatsapp", channel_account_id=account,
        recipient_ref="recipient-1", origin=ResponseOrigin(origin),
        ownership_version=version, kind=ResponseKind.TEXT,
        text="Hello!",
    )
    notification = Notification(
        notification_id="notify-1",tenant_id="tenant-a",job_id="j1",
        channel="whatsapp",recipient_ref="recipient-1",
        status=NotificationStatus.IN_FLIGHT, attempts=1,lease_token="lease",
    )
    message = AgentMessage(
        source="rkjo.agent",target="rkjo.omnichannel.delivery",
        message_type="omnichannel.response.requested",
        payload={"omnichannel_response":response.model_dump(mode="json")},
        metadata={"tenant_id":tenant,"operator_id":operator_id},
    )
    return notification,message


def test_valid_agent_reply_uses_existing_channel_adapter(context):
    url,router,route = context
    downstream,policy = Sender(),Policy()
    guard = OwnershipFencedChannelAdapter(database_url=url,downstream=downstream,policy=policy)
    assert guard.send(notification=build(route)[0],message=build(route)[1]) == "provider-out-1"
    assert len(downstream.calls) == 1
    assert policy.calls == 1


def test_agent_reply_cannot_escape_after_human_takeover(context):
    url,router,route = context
    router.transfer(tenant_id="tenant-a",conversation_id=route.conversation_id,
                    expected_version=0,operator_id="operator-1")
    sender = Sender()
    guard = OwnershipFencedChannelAdapter(database_url=url,downstream=sender,policy=Policy())
    notification,message = build(route)
    with pytest.raises(ObsoleteConversationResponse):
        guard.send(notification=notification,message=message)
    assert sender.calls == []


def test_human_reply_requires_assigned_operator_and_fresh_version(context):
    url,router,route = context
    router.transfer(tenant_id="tenant-a",conversation_id=route.conversation_id,
                    expected_version=0,operator_id="operator-1")
    sender = Sender()
    guard = OwnershipFencedChannelAdapter(database_url=url,downstream=sender,policy=Policy())
    notification,message = build(route,origin="human",version=1,operator_id="intruder")
    with pytest.raises(PermissionError,match="Assigned operator"):
        guard.send(notification=notification,message=message)
    notification,message = build(route,origin="human",version=1,operator_id="operator-1")
    assert guard.send(notification=notification,message=message) == "provider-out-1"
    assert len(sender.calls) == 1


def test_tenant_account_and_channel_policy_fail_closed(context):
    url,router,route = context
    sender,policy = Sender(),Policy()
    guard = OwnershipFencedChannelAdapter(database_url=url,downstream=sender,policy=policy)
    for notification,message in (
        build(route,tenant="tenant-b"),
        build(route,account="unbound-account"),
    ):
        with pytest.raises(PermissionError):
            guard.send(notification=notification,message=message)
    policy.denied=True
    notification,message=build(route)
    with pytest.raises(PermissionError,match="Channel policy"):
        guard.send(notification=notification,message=message)
    assert sender.calls == []



def test_response_cannot_be_sent_to_different_contact(context):
    url,router,route = context
    sender = Sender()
    guard = OwnershipFencedChannelAdapter(database_url=url,downstream=sender,policy=Policy())
    notification,message = build(route)
    notification = Notification(
        notification_id=notification.notification_id,tenant_id=notification.tenant_id,
        job_id=notification.job_id,channel=notification.channel,
        recipient_ref="another-contact",status=NotificationStatus.IN_FLIGHT,
        attempts=1,lease_token="lease",
    )
    message.payload["omnichannel_response"]["recipient_ref"] = "another-contact"
    with pytest.raises(PermissionError,match="recipient"):
        guard.send(notification=notification,message=message)
    assert sender.calls == []


def test_missing_contract_cannot_bypass_guard(context):
    url,router,route = context
    sender = Sender()
    guard = OwnershipFencedChannelAdapter(database_url=url,downstream=sender,policy=Policy())
    notification,message=build(route)
    message.payload = {"text":"unguarded"}
    with pytest.raises(ValueError,match="Missing omnichannel_response"):
        guard.send(notification=notification,message=message)
    assert sender.calls == []


def test_human_takeover_waits_until_provider_call_finishes(context):
    url,router,route = context
    entered,release = Event(),Event()
    sender = Sender(entered=entered,release=release)
    guard = OwnershipFencedChannelAdapter(database_url=url,downstream=sender,policy=Policy())
    notification,message=build(route)
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_send = executor.submit(guard.send,notification=notification,message=message)
        assert entered.wait(timeout=5)
        future_transfer = executor.submit(
            router.transfer,tenant_id="tenant-a",conversation_id=route.conversation_id,
            expected_version=0,operator_id="operator-1",
        )
        try:
            # Concurrent UPDATE must wait for the send's FOR SHARE lock.
            with psycopg.connect(url) as independent:
                independent.execute("SET LOCAL lock_timeout = '150ms'")
                with pytest.raises(psycopg.errors.LockNotAvailable):
                    independent.execute("""
                        UPDATE omni_conversations
                        SET ownership_version=ownership_version+1
                        WHERE tenant_id=%s AND conversation_id=%s
                    """, ("tenant-a",route.conversation_id))
            assert not future_transfer.done()
        finally:
            release.set()
        assert future_send.result(timeout=5) == "provider-out-1"
        assert future_transfer.result(timeout=5).mode.value == "human"
    assert len(sender.calls) == 1

def test_guarded_send_registers_provider_reference_in_delivery_ledger(context):
    from rkjo_kernel.omnichannel.delivery_ledger import PostgreSQLDeliveryLedger
    url, router, route = context
    ledger = PostgreSQLDeliveryLedger(url)
    ledger.initialize_schema()
    sender = Sender()
    guard = OwnershipFencedChannelAdapter(
        database_url=url, downstream=sender, policy=Policy(),
        delivery_ledger=ledger,
    )
    notification, message = build(route)
    assert guard.send(notification=notification, message=message) == "provider-out-1"
    state = ledger.load(tenant_id="tenant-a", notification_id="notify-1")
    assert state.provider_message_id == "provider-out-1"
    assert state.channel_account_id == "phone-a"
    assert ledger.load(tenant_id="tenant-b", notification_id="notify-1") is None
    assert guard.send(notification=notification, message=message) == "provider-out-1"
    assert len(sender.calls) == 2
