"""OMNI-015.5: atomic dispatch fencing under PostgreSQL concurrency."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.types.json import Jsonb

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.multimodal.postgres_notifications import PostgreSQLNotificationStore
from rkjo_kernel.omnichannel.delivery_ledger import PostgreSQLDeliveryLedger

NOW = datetime.now(timezone.utc)


@pytest.fixture
def stack():
    url = os.getenv("RKJO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("RKJO_TEST_DATABASE_URL required")
    if "test" not in conninfo_to_dict(url).get("dbname","").lower():
        pytest.fail("Dedicated test database required")
    schema = "rkjo_omni_claim_" + uuid4().hex
    with psycopg.connect(url) as conn:
        conn.execute('CREATE SCHEMA "'+schema+'"')
    scoped = make_conninfo(url, options="-c search_path="+schema)
    try:
        store = PostgreSQLNotificationStore(scoped, max_attempts=3)
        store.initialize_schema()
        ledger = PostgreSQLDeliveryLedger(scoped)
        ledger.initialize_schema()
        yield scoped, store, ledger
    finally:
        with psycopg.connect(url) as conn:
            conn.execute('DROP SCHEMA "'+schema+'" CASCADE')


def insert(url, ident, *, status="retry", attempts=1, tenant="tenant-a",
           account="phone-a", provider_ref=None, omni=True, expired=True):
    response = {
        "notification_id": ident, "tenant_id": tenant,
        "channel_account_id": account, "recipient_ref": "customer-a",
    }
    message = AgentMessage(
        message_id=ident, source="rkjo.agent", target="rkjo.delivery",
        message_type="omnichannel.response.requested" if omni else "multimodal.notification.requested",
        payload=({"omnichannel_response": response} if omni else {"job_id":"job"}),
        metadata={"tenant_id":tenant},
    )
    payload = message.model_dump(mode="json")
    lease = "lease" if status == "in_flight" else None
    with psycopg.connect(url) as conn:
        conn.execute("""
            INSERT INTO multimodal_notifications
             (notification_id,tenant_id,job_id,channel,recipient_ref,
              message_payload,status,attempts,lease_token,lease_until,provider_ref)
            VALUES (%s,%s,'j','whatsapp','customer-a',%s,%s,%s,%s,%s,%s)
        """, (ident,tenant,Jsonb(payload),status,attempts,lease,
              (NOW - timedelta(seconds=5) if expired
               else NOW + timedelta(seconds=60)) if lease else None,
              provider_ref))


def status(url, ident):
    with psycopg.connect(url) as conn:
        return conn.execute("""
            SELECT status,last_error,attempts,provider_ref
            FROM multimodal_notifications WHERE notification_id=%s
        """,(ident,)).fetchone()


def test_due_retry_without_provider_proof_is_fenced(stack):
    url,store,_=stack
    insert(url,"unknown")
    assert store.claim_due(now=NOW,lease_seconds=10) is None
    assert status(url,"unknown")==("failed","UncertainProviderAcceptance",1,None)


def test_expired_lease_without_proof_is_fenced(stack):
    url,store,_=stack
    insert(url,"expired",status="in_flight")
    assert store.claim_due(now=NOW,lease_seconds=10) is None
    assert status(url,"expired")[0:2]==("failed","UncertainProviderAcceptance")


def test_verified_provider_acceptance_is_reconciled_atomically(stack):
    url,store,ledger=stack
    insert(url,"confirmed")
    ledger.register_sent(tenant_id="tenant-a",notification_id="confirmed",
                         channel="whatsapp",channel_account_id="phone-a",
                         provider_message_id="wamid-1")
    assert store.claim_due(now=NOW,lease_seconds=10) is None
    assert status(url,"confirmed")==("sent",None,1,"wamid-1")


def test_concurrent_workers_never_reclaim_uncertain_send(stack):
    url,store,_=stack
    insert(url,"uncertain")
    with ThreadPoolExecutor(max_workers=3) as pool:
        claims=list(pool.map(lambda _: store.claim_due(now=NOW,lease_seconds=10),range(3)))
    assert claims == [None,None,None]
    assert status(url,"uncertain")[0]=="failed"


def test_tenant_account_binding_mismatch_is_not_accepted(stack):
    url,store,ledger=stack
    insert(url,"wrong-account")
    ledger.register_sent(tenant_id="tenant-a",notification_id="wrong-account",
                         channel="whatsapp",channel_account_id="other-phone",
                         provider_message_id="wamid-other")
    assert store.claim_due(now=NOW,lease_seconds=10) is None
    assert status(url,"wrong-account")[0]=="failed"


def test_first_attempt_still_claimable_without_prior_proof(stack):
    url,store,_=stack
    insert(url,"new",status="pending",attempts=0)
    claimed = store.claim_due(now=NOW,lease_seconds=10)
    assert claimed is not None
    notification, message = claimed
    assert notification.notification_id == "new"
    assert notification.attempts == 1
    assert message.payload["omnichannel_response"]["notification_id"] == "new"


def test_legacy_multimodal_retry_keeps_existing_behavior(stack):
    url,store,_=stack
    insert(url,"legacy",omni=False)
    claimed = store.claim_due(now=NOW,lease_seconds=10)
    assert claimed is not None
    notification, message = claimed
    assert notification.notification_id == "legacy"
    assert notification.attempts == 2
    assert message.payload["job_id"] == "job"


def test_first_attempt_with_existing_provider_proof_is_not_sent(stack):
    url,store,ledger=stack
    insert(url,"early-proof",status="pending",attempts=0)
    ledger.register_sent(tenant_id="tenant-a",notification_id="early-proof",
                         channel="whatsapp",channel_account_id="phone-a",
                         provider_message_id="wamid-early")
    assert store.claim_due(now=NOW,lease_seconds=10) is None
    assert status(url,"early-proof")[0] == "sent"
