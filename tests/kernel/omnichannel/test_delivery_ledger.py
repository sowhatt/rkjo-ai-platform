"""OMNI-013.3: real PostgreSQL receipts, tenant isolation and replay safety."""
import os
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from rkjo_kernel.omnichannel.delivery_ledger import PostgreSQLDeliveryLedger, DeliveryReceiptHandler
from rkjo_kernel.omnichannel.inbound import InboundKind, VerifiedInbound


@pytest.fixture
def ledger():
    url = os.getenv("RKJO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires RKJO_TEST_DATABASE_URL.")
    if "test" not in conninfo_to_dict(url).get("dbname", "").lower():
        pytest.fail("Isolated test database required.")
    schema = "rkjo_omni_receipt_" + uuid4().hex
    with psycopg.connect(url) as conn:
        conn.execute('CREATE SCHEMA "' + schema + '"')
    scoped = make_conninfo(url, options="-c search_path=" + schema)
    try:
        obj = PostgreSQLDeliveryLedger(scoped)
        obj.initialize_schema()
        yield obj
    finally:
        with psycopg.connect(url) as conn:
            conn.execute('DROP SCHEMA "' + schema + '" CASCADE')


def receipt(status="sent", timestamp="1700000001", *,
            tenant="tenant-a", account="phone-a", message="provider-1",
            failure_code=None):
    data = {"id": message, "status": status, "timestamp": timestamp}
    if failure_code is not None:
        data["errors"] = [{"code": failure_code}]
    return VerifiedInbound(
        tenant_id=tenant, channel="whatsapp", channel_account_id=account,
        provider_event_id=f"status:{message}:{status}:{timestamp}",
        kind=InboundKind.DELIVERY_RECEIPT, payload={"event": data},
    )


def bind(ledger):
    ledger.register_sent(
        tenant_id="tenant-a", notification_id="notify-1",
        channel="whatsapp", channel_account_id="phone-a",
        provider_message_id="provider-1",
    )


def test_sent_delivered_read_and_replays_are_idempotent(ledger):
    bind(ledger)
    handler = DeliveryReceiptHandler(ledger)
    for status, timestamp in (("sent", "1700000001"),
                              ("delivered", "1700000002"),
                              ("read", "1700000003")):
        event = receipt(status, timestamp)
        handler.handle(event)
        handler.handle(event)
    snapshot = ledger.load(tenant_id="tenant-a", notification_id="notify-1")
    assert snapshot.status.value == "read"
    assert snapshot.failure_code is None
    assert ledger.record(receipt("sent", "1700000001")).status.value == "read"


def test_out_of_order_status_never_regresses(ledger):
    bind(ledger)
    assert ledger.record(receipt("read", "1700000003")).status.value == "read"
    assert ledger.record(receipt("delivered", "1700000002")).status.value == "read"
    assert ledger.record(receipt("failed", "1700000004", failure_code=131000)).status.value == "read"


def test_failed_before_delivery_can_be_corrected_by_later_delivered(ledger):
    bind(ledger)
    failed = ledger.record(receipt("failed", "1700000001", failure_code=131000))
    assert failed.status.value == "failed"
    assert failed.failure_code == "131000"
    assert ledger.record(receipt("delivered", "1700000002")).status.value == "delivered"


def test_unknown_message_and_cross_tenant_cannot_modify_ledger(ledger):
    bind(ledger)
    with pytest.raises(LookupError):
        ledger.record(receipt(tenant="tenant-b"))
    with pytest.raises(LookupError):
        ledger.record(receipt(account="phone-b"))
    with pytest.raises(LookupError):
        ledger.record(receipt(message="unregistered"))
    assert ledger.load(tenant_id="tenant-a", notification_id="notify-1").status is None
    assert ledger.load(tenant_id="tenant-b", notification_id="notify-1") is None


def test_bindings_cannot_be_replaced_or_reused(ledger):
    bind(ledger)
    bind(ledger)
    with pytest.raises(ValueError, match="binding conflict"):
        ledger.register_sent(
            tenant_id="tenant-a", notification_id="notify-1",
            channel="whatsapp", channel_account_id="phone-a",
            provider_message_id="changed",
        )
    with pytest.raises(ValueError, match="bound elsewhere"):
        ledger.register_sent(
            tenant_id="tenant-a", notification_id="notify-2",
            channel="whatsapp", channel_account_id="phone-a",
            provider_message_id="provider-1",
        )


def test_receipts_never_accept_messages_or_wrong_event_identity(ledger):
    bind(ledger)
    message = receipt()
    message = VerifiedInbound(
        tenant_id=message.tenant_id, channel=message.channel,
        channel_account_id=message.channel_account_id,
        provider_event_id=message.provider_event_id,
        kind=InboundKind.USER_MESSAGE, payload=message.payload,
    )
    with pytest.raises(ValueError, match="Only verified"):
        ledger.record(message)
    raw = receipt()
    altered = VerifiedInbound(
        tenant_id=raw.tenant_id, channel=raw.channel,
        channel_account_id=raw.channel_account_id,
        provider_event_id="forged", kind=raw.kind, payload=raw.payload,
    )
    with pytest.raises(ValueError, match="does not match"):
        ledger.record(altered)


def test_receipt_replay_with_different_failure_data_is_conflict(ledger):
    bind(ledger)
    ledger.record(receipt("failed", "1700000001", failure_code=100))
    with pytest.raises(ValueError, match="Conflicting receipt replay"):
        ledger.record(receipt("failed", "1700000001", failure_code=200))
