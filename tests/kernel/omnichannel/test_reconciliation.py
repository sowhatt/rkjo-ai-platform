"""OMNI-015.3: never resend uncertain provider operations during reconciliation."""
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.types.json import Jsonb

from rkjo_kernel.multimodal.postgres_notifications import PostgreSQLNotificationStore
from rkjo_kernel.omnichannel.delivery_ledger import PostgreSQLDeliveryLedger
from rkjo_kernel.omnichannel.reconciliation import OmnichannelDeliveryReconciler


NOW = datetime.now(timezone.utc)


@pytest.fixture
def system():
    url = os.getenv("RKJO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires RKJO_TEST_DATABASE_URL.")
    if "test" not in conninfo_to_dict(url).get("dbname","").lower():
        pytest.fail("Dedicated test DB required.")
    schema = "rkjo_reconcile_" + uuid4().hex
    with psycopg.connect(url) as conn:
        conn.execute('CREATE SCHEMA "' + schema + '"')
    scoped = make_conninfo(url, options="-c search_path=" + schema)
    try:
        PostgreSQLNotificationStore(scoped).initialize_schema()
        ledger = PostgreSQLDeliveryLedger(scoped)
        ledger.initialize_schema()
        yield scoped, ledger, OmnichannelDeliveryReconciler(scoped)
    finally:
        with psycopg.connect(url) as conn:
            conn.execute('DROP SCHEMA "' + schema + '" CASCADE')


def insert(url, ident, *, tenant="tenant-a", status="in_flight",
           account="phone-a", expires=True, omni=True, provider_ref=None):
    response = {
        "notification_id": ident,"tenant_id":tenant,"channel_account_id":account,
        "recipient_ref":"customer-a",
    }
    payload = {"payload": {"omnichannel_response": response}} if omni else {"payload":{"job_id":"job"}}
    lease = "lease-a" if status == "in_flight" else None
    until = NOW - timedelta(minutes=2) if expires else NOW + timedelta(minutes=2)
    with psycopg.connect(url) as conn:
        conn.execute("""
            INSERT INTO multimodal_notifications
            (notification_id,tenant_id,job_id,channel,recipient_ref,
             message_payload,status,attempts,lease_token,lease_until,provider_ref)
            VALUES (%s,%s,'job','whatsapp','customer-a',%s,%s,1,%s,%s,%s)
        """, (ident,tenant,Jsonb(payload),status,lease,until if lease else None,provider_ref))


def test_confirmed_provider_send_is_repaired_without_resend(system):
    url,ledger,reconciler = system
    insert(url,"n1")
    ledger.register_sent(
        tenant_id="tenant-a",notification_id="n1",channel="whatsapp",
        channel_account_id="phone-a",provider_message_id="wamid-1",
    )
    report = reconciler.reconcile(tenant_id="tenant-a",now=NOW)
    assert report.repaired == 1
    with psycopg.connect(url) as conn:
        state = conn.execute("""
            SELECT status,provider_ref,lease_token,lease_until
            FROM multimodal_notifications WHERE notification_id='n1'
        """).fetchone()
    assert state == ("sent","wamid-1",None,None)
    assert reconciler.reconcile(tenant_id="tenant-a",now=NOW).repaired == 0


def test_active_lease_not_overwritten_even_if_binding_exists(system):
    url,ledger,reconciler = system
    insert(url,"n1",expires=False)
    ledger.register_sent(
        tenant_id="tenant-a",notification_id="n1",channel="whatsapp",
        channel_account_id="phone-a",provider_message_id="wamid-1",
    )
    report = reconciler.reconcile(tenant_id="tenant-a",now=NOW)
    assert report.repaired == 0
    assert report.provider_confirmed_uncommitted == 1
    with psycopg.connect(url) as conn:
        assert conn.execute(
            "SELECT status FROM multimodal_notifications WHERE notification_id='n1'"
        ).fetchone()[0] == "in_flight"


def test_unknown_provider_reference_is_reported_without_mutation(system):
    url,_,reconciler = system
    insert(url,"unknown")
    report = reconciler.reconcile(tenant_id="tenant-a",now=NOW)
    assert report.repaired == 0
    assert report.expired_unconfirmed == 1
    with psycopg.connect(url) as conn:
        assert conn.execute(
            "SELECT status FROM multimodal_notifications WHERE notification_id='unknown'"
        ).fetchone()[0] == "in_flight"


def test_cross_tenant_and_account_mismatch_never_reconciles(system):
    url,ledger,reconciler = system
    insert(url,"n1",tenant="tenant-a")
    insert(url,"n2",tenant="tenant-b")
    ledger.register_sent(
        tenant_id="tenant-a",notification_id="n1",channel="whatsapp",
        channel_account_id="wrong-phone",provider_message_id="wamid-a",
    )
    ledger.register_sent(
        tenant_id="tenant-b",notification_id="n2",channel="whatsapp",
        channel_account_id="phone-a",provider_message_id="wamid-b",
    )
    assert reconciler.reconcile(tenant_id="tenant-a",now=NOW).repaired == 0
    assert reconciler.reconcile(tenant_id="tenant-b",now=NOW).repaired == 1
    with psycopg.connect(url) as conn:
        assert conn.execute(
            "SELECT status FROM multimodal_notifications WHERE notification_id='n1'"
        ).fetchone()[0] == "in_flight"


def test_multimodal_notification_not_touched_and_sent_without_binding_flagged(system):
    url,_,reconciler = system
    insert(url,"legacy",omni=False)
    insert(url,"sent-no-ledger",status="sent")
    report = reconciler.reconcile(tenant_id="tenant-a",now=NOW)
    assert report.repaired == 0
    assert report.sent_without_binding == 1
    assert report.expired_unconfirmed == 0
    with psycopg.connect(url) as conn:
        assert conn.execute(
            "SELECT status FROM multimodal_notifications WHERE notification_id='legacy'"
        ).fetchone()[0] == "in_flight"


def test_mismatched_provider_ref_not_overwritten(system):
    url,ledger,reconciler = system
    insert(url,"n1",status="retry",provider_ref="other-provider")
    ledger.register_sent(
        tenant_id="tenant-a",notification_id="n1",channel="whatsapp",
        channel_account_id="phone-a",provider_message_id="wamid-1",
    )
    report = reconciler.reconcile(tenant_id="tenant-a",now=NOW)
    assert report.repaired == 0
    assert report.provider_confirmed_uncommitted == 1
    with psycopg.connect(url) as conn:
        assert conn.execute(
            "SELECT provider_ref FROM multimodal_notifications WHERE notification_id='n1'"
        ).fetchone()[0] == "other-provider"
