"""OMNI-013.2: real PostgreSQL isolated ownership + conversation routing."""
from datetime import datetime, timezone
import os
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from rkjo_kernel.omnichannel.contracts import ChannelResponse, ResponseOrigin, ResponseKind
from rkjo_kernel.omnichannel.conversation_router import PostgreSQLConversationRouter, ConversationRoutingHandler
from rkjo_kernel.omnichannel.inbound import InboundKind, VerifiedInbound


@pytest.fixture
def router():
    url = os.getenv("RKJO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires RKJO_TEST_DATABASE_URL.")
    if "test" not in conninfo_to_dict(url).get("dbname", "").lower():
        pytest.fail("Dedicated test database required.")
    schema = "rkjo_omni_owner_" + uuid4().hex
    with psycopg.connect(url) as conn:
        conn.execute('CREATE SCHEMA "' + schema + '"')
    scoped = make_conninfo(url, options="-c search_path=" + schema)
    try:
        instance = PostgreSQLConversationRouter(scoped)
        instance.initialize_schema()
        yield instance
    finally:
        with psycopg.connect(url) as conn:
            conn.execute('DROP SCHEMA "' + schema + '" CASCADE')


def whatsapp(*, ident="msg1", sender="user-1", tenant="tenant-a", kind=InboundKind.USER_MESSAGE, timestamp="1700000000"):
    return VerifiedInbound(
        channel="whatsapp", channel_account_id="phone-1", tenant_id=tenant,
        provider_event_id=ident, kind=kind,
        payload={"event": {"from": sender, "timestamp": timestamp}},
    )


def response(routed, *, origin="agent", version=None):
    return ChannelResponse(
        notification_id="n1", tenant_id=routed.tenant_id,
        conversation_id=routed.conversation_id, channel=routed.channel,
        channel_account_id=routed.channel_account_id, recipient_ref="recipient",
        origin=ResponseOrigin(origin), ownership_version=(
            routed.ownership_version if version is None else version
        ), kind=ResponseKind.TEXT, text="Hello",
    )


def test_agent_message_is_routed_once_and_replay_keeps_version(router):
    first = router.route(whatsapp())
    assert first.destination == "agent"
    assert first.ownership_version == 0
    assert router.route(whatsapp()) == first
    state = router.ownership(tenant_id="tenant-a", conversation_id=first.conversation_id)
    assert state.last_inbound_at == datetime.fromtimestamp(1700000000, tz=timezone.utc)
    assert router.authorize_response(response(first))


def test_human_takeover_reroutes_next_message_and_fences_old_agent(router):
    first = router.route(whatsapp())
    human = router.transfer(tenant_id="tenant-a", conversation_id=first.conversation_id,
                            expected_version=0, operator_id="operator-1")
    assert human.mode.value == "human"
    assert human.ownership_version == 1
    assert not router.authorize_response(response(first))
    second = router.route(whatsapp(ident="msg2", timestamp="1700000010"))
    assert second.destination == "human"
    assert second.ownership_version == 1
    assert router.authorize_response(response(second, origin="human"))
    assert not router.authorize_response(response(second, origin="agent"))
    assert router.route(whatsapp()) == first
    assert router.ownership(tenant_id="tenant-a", conversation_id=first.conversation_id).last_inbound_at == (
        datetime.fromtimestamp(1700000010, tz=timezone.utc)
    )


def test_release_returns_to_agent_and_fences_human_response(router):
    first = router.route(whatsapp())
    router.transfer(tenant_id="tenant-a", conversation_id=first.conversation_id,
                    expected_version=0, operator_id="operator-1")
    second = router.route(whatsapp(ident="msg2"))
    released = router.transfer(tenant_id="tenant-a", conversation_id=first.conversation_id,
                               expected_version=1, operator_id=None)
    assert released.mode.value == "agent"
    assert released.ownership_version == 2
    assert not router.authorize_response(response(second, origin="human"))
    third = router.route(whatsapp(ident="msg3"))
    assert third.destination == "agent"
    assert third.ownership_version == 2


def test_wrong_tenant_stale_version_and_unauthorized_conversation_rejected(router):
    routed = router.route(whatsapp())
    with pytest.raises(ValueError, match="wrong tenant"):
        router.transfer(tenant_id="tenant-b", conversation_id=routed.conversation_id,
                        expected_version=0, operator_id="operator-1")
    assert not router.authorize_response(response(routed).model_copy(update={"tenant_id": "tenant-b"}))
    router.transfer(tenant_id="tenant-a", conversation_id=routed.conversation_id,
                    expected_version=0, operator_id="operator-1")
    with pytest.raises(ValueError, match="stale"):
        router.transfer(tenant_id="tenant-a", conversation_id=routed.conversation_id,
                        expected_version=0, operator_id="operator-2")


def test_receipts_cannot_update_last_inbound_at(router):
    first = router.route(whatsapp())
    with pytest.raises(ValueError, match="Only user messages"):
        ConversationRoutingHandler(router).handle(whatsapp(
            ident="receipt", kind=InboundKind.DELIVERY_RECEIPT,
            timestamp="1900000000",
        ))
    state = router.ownership(tenant_id="tenant-a", conversation_id=first.conversation_id)
    assert state.last_inbound_at == datetime.fromtimestamp(1700000000, tz=timezone.utc)


def test_out_of_order_user_message_cannot_move_whatsapp_window_backwards(router):
    first = router.route(whatsapp(timestamp="1700000100"))
    router.route(whatsapp(ident="older", timestamp="1700000000"))
    assert router.ownership(tenant_id="tenant-a", conversation_id=first.conversation_id).last_inbound_at == (
        datetime.fromtimestamp(1700000100, tz=timezone.utc)
    )


def test_telegram_chat_is_tenant_scoped_and_not_mixed_with_whatsapp(router):
    first = router.route(whatsapp())
    tg = VerifiedInbound(
        channel="telegram", channel_account_id="bot-a", tenant_id="tenant-a",
        provider_event_id="update1", kind=InboundKind.USER_MESSAGE,
        payload={"message": {"chat": {"id": 1234}, "date": 1700000000}},
    )
    result = router.route(tg)
    assert result.conversation_id != first.conversation_id
    assert result.destination == "agent"
    assert router.ownership(tenant_id="tenant-a", conversation_id=result.conversation_id).origin_channel == "telegram"
