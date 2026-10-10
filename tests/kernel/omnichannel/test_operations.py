"""OMNI-015.4: operational read model and safe quarantine integration."""
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.types.json import Jsonb

from rkjo_kernel.multimodal.postgres_notifications import PostgreSQLNotificationStore
from rkjo_kernel.omnichannel.delivery_ledger import PostgreSQLDeliveryLedger
from rkjo_kernel.omnichannel.inbound_processor import PostgreSQLInboundProcessorStore
from rkjo_kernel.omnichannel.postgres_inbox import PostgreSQLInboundInbox
from rkjo_kernel.omnichannel.conversation_router import PostgreSQLConversationRouter
from rkjo_kernel.omnichannel.operations import PostgreSQLOmnichannelOperations
from rkjo_kernel.omnichannel.reconciliation import OmnichannelDeliveryReconciler

NOW = datetime.now(timezone.utc)


@pytest.fixture
def stack():
    url = os.getenv("RKJO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("RKJO_TEST_DATABASE_URL required.")
    if "test" not in conninfo_to_dict(url).get("dbname","").lower():
        pytest.fail("Dedicated test DB required.")
    schema = "rkjo_omni_operations_" + uuid4().hex
    with psycopg.connect(url) as conn:
        conn.execute('CREATE SCHEMA "' + schema + '"')
    scoped = make_conninfo(url, options="-c search_path=" + schema)
    try:
        PostgreSQLInboundInbox(scoped).initialize_schema()
        PostgreSQLInboundProcessorStore(scoped).initialize_schema()
        PostgreSQLConversationRouter(scoped).initialize_schema()
        PostgreSQLNotificationStore(scoped).initialize_schema()
        PostgreSQLDeliveryLedger(scoped).initialize_schema()
        yield scoped, PostgreSQLOmnichannelOperations(scoped), OmnichannelDeliveryReconciler(scoped)
    finally:
        with psycopg.connect(url) as conn:
            conn.execute('DROP SCHEMA "' + schema + '" CASCADE')


def put(url, identity, *, tenant="tenant-a", state="retry", attempts=1,
        expires=True, omni=True):
    payload = {"payload":{"omnichannel_response":{
        "notification_id":identity, "tenant_id":tenant,
        "channel_account_id":"phone-a", "recipient_ref":"customer-a",
    }}} if omni else {"payload":{"job_id":"job"}}
    lease = "active-lease" if state == "in_flight" else None
    with psycopg.connect(url) as conn:
        conn.execute("""
            INSERT INTO multimodal_notifications
              (notification_id,tenant_id,job_id,channel,recipient_ref,
               message_payload,status,attempts,lease_token,lease_until)
            VALUES (%s,%s,'j','whatsapp','customer-a',%s,%s,%s,%s,%s)
        """, (
            identity,tenant,Jsonb(payload),state,attempts,lease,
            (NOW-timedelta(seconds=10) if expires else NOW+timedelta(seconds=60))
            if lease else None,
        ))


def test_snapshot_is_tenant_scoped_and_does_not_return_payloads(stack):
    url,ops,_=stack
    put(url,"n1")
    put(url,"n2",tenant="tenant-b")
    report=ops.snapshot(tenant_id="tenant-a",now=NOW)
    assert report.outbound.pending == 1
    assert report.uncertain_outbound == 1
    assert report.delivery_receipts == 0
    assert ops.snapshot(tenant_id="tenant-b",now=NOW).outbound.pending == 1


def test_quarantine_expired_or_retry_uncertain_and_is_idempotent(stack):
    url,ops,reconciler=stack
    put(url,"retry")
    put(url,"expired",state="in_flight")
    assert reconciler.quarantine_uncertain(tenant_id="tenant-a",now=NOW) == 2
    assert reconciler.quarantine_uncertain(tenant_id="tenant-a",now=NOW) == 0
    with psycopg.connect(url) as conn:
        rows=conn.execute("""
            SELECT status,last_error,lease_token,next_attempt_at
            FROM multimodal_notifications WHERE tenant_id='tenant-a'
        """).fetchall()
    assert len(rows)==2
    assert all(row == ("failed","UncertainProviderAcceptance",None,None) for row in rows)
    assert ops.snapshot(tenant_id="tenant-a",now=NOW).outbound.failed == 2


def test_active_lease_and_first_attempt_are_not_quarantined(stack):
    url,_,reconciler=stack
    put(url,"active",state="in_flight",expires=False)
    put(url,"new",state="pending",attempts=0)
    assert reconciler.quarantine_uncertain(tenant_id="tenant-a",now=NOW)==0
    with psycopg.connect(url) as conn:
        assert conn.execute(
            "SELECT count(*) FROM multimodal_notifications WHERE status='failed'"
        ).fetchone()[0]==0


def test_provider_proof_is_not_quarantined_and_can_reconcile(stack):
    url,ops,reconciler=stack
    put(url,"accepted")
    ledger=PostgreSQLDeliveryLedger(url)
    ledger.register_sent(
        tenant_id="tenant-a",notification_id="accepted",
        channel="whatsapp",channel_account_id="phone-a",
        provider_message_id="wamid-accepted",
    )
    assert reconciler.quarantine_uncertain(tenant_id="tenant-a",now=NOW)==0
    assert reconciler.reconcile(tenant_id="tenant-a",now=NOW).repaired==1
    assert ops.snapshot(tenant_id="tenant-a",now=NOW).uncertain_outbound==0


def test_other_tenant_and_non_omnichannel_work_are_untouched(stack):
    url,ops,reconciler=stack
    put(url,"other-tenant",tenant="tenant-b")
    put(url,"legacy",omni=False)
    assert reconciler.quarantine_uncertain(tenant_id="tenant-a",now=NOW)==0
    assert ops.snapshot(tenant_id="tenant-a",now=NOW).uncertain_outbound==0
    with psycopg.connect(url) as conn:
        assert conn.execute(
            "SELECT count(*) FROM multimodal_notifications WHERE status='retry'"
        ).fetchone()[0]==2


def test_invalid_tenant_or_naive_clock_is_rejected(stack):
    _,ops,reconciler=stack
    with pytest.raises(ValueError):
        ops.snapshot(tenant_id="",now=NOW)
    with pytest.raises(ValueError):
        ops.snapshot(tenant_id="tenant-a",now=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError):
        reconciler.quarantine_uncertain(tenant_id="",now=NOW)
