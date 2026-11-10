"""OMNI-013.1 integration in a dedicated temporary PostgreSQL schema."""
from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from rkjo_kernel.omnichannel.inbound import InboundKind, VerifiedInbound
from rkjo_kernel.omnichannel.postgres_inbox import PostgreSQLInboundInbox
from rkjo_kernel.omnichannel.inbound_processor import (
    InboundProcessingWorker, PostgreSQLInboundProcessorStore,
)

NOW = datetime.now(timezone.utc)


@pytest.fixture
def stores():
    url = os.getenv("RKJO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires RKJO_TEST_DATABASE_URL.")
    if "test" not in conninfo_to_dict(url).get("dbname", "").lower():
        pytest.fail("Tests must use a dedicated test database.")
    schema = "rkjo_omni_lease_" + uuid4().hex
    with psycopg.connect(url) as conn:
        conn.execute('CREATE SCHEMA "' + schema + '"')
    scoped = make_conninfo(url, options="-c search_path=" + schema)
    try:
        inbox = PostgreSQLInboundInbox(scoped)
        inbox.initialize_schema()
        store = PostgreSQLInboundProcessorStore(scoped, max_attempts=3)
        store.initialize_schema()
        yield inbox, store
    finally:
        with psycopg.connect(url) as conn:
            conn.execute('DROP SCHEMA "' + schema + '" CASCADE')


def add(inbox, *, kind=InboundKind.USER_MESSAGE):
    ident = uuid4().hex
    event = VerifiedInbound(
        tenant_id="tenant-" + ident,
        channel="whatsapp", channel_account_id="phone-" + ident,
        provider_event_id="evt-" + ident, kind=kind, payload={"id": ident},
    )
    assert inbox.accept_once(event)
    return event


def test_claim_leased_once_and_stale_ack_is_rejected(stores):
    inbox, store = stores
    event = add(inbox)
    first = store.claim_due(now=NOW, lease_seconds=10)
    assert first.event == event
    assert store.claim_due(now=NOW) is None
    with pytest.raises(ValueError, match="Stale"):
        store.mark_processed(type(first)(event=first.event, lease_token="wrong", attempt=first.attempt))
    store.mark_processed(first)
    with pytest.raises(ValueError, match="Stale"):
        store.mark_processed(first)
    assert store.claim_due(now=NOW + timedelta(hours=1)) is None


def test_worker_routes_receipt_without_agent_invocation(stores):
    inbox, store = stores
    receipt = add(inbox, kind=InboundKind.DELIVERY_RECEIPT)
    class Handler:
        def __init__(self):
            self.received = []
        def handle(self, event):
            self.received.append(event)
    agent = Handler()
    status = Handler()
    worker = InboundProcessingWorker(store=store, user_messages=agent, delivery_receipts=status)
    assert worker.run_once(now=NOW)
    assert status.received == [receipt]
    assert agent.received == []
    assert not worker.run_once(now=NOW)


def test_crash_before_ack_retries_then_stale_token_cannot_commit(stores):
    inbox, store = stores
    event = add(inbox)
    first = store.claim_due(now=NOW, lease_seconds=2)
    second = store.claim_due(now=NOW + timedelta(seconds=3), lease_seconds=10)
    assert first.event == second.event == event
    assert second.attempt == first.attempt + 1
    with pytest.raises(ValueError, match="Stale"):
        store.mark_processed(first)
    store.mark_processed(second)
    assert store.claim_due(now=NOW + timedelta(hours=1)) is None


def test_retry_limit_blocks_future_claims(stores):
    inbox, store = stores
    add(inbox)
    for idx in range(3):
        when = NOW + timedelta(seconds=idx*10)
        claim = store.claim_due(now=when, lease_seconds=2)
        assert claim is not None and claim.attempt == idx + 1
        store.mark_failed(claim, now=when, error="ProviderFailure", retry_delay_seconds=1)
    assert store.claim_due(now=NOW + timedelta(hours=1)) is None


def test_invalid_lease_inputs_rejected(stores):
    inbox, store = stores
    add(inbox)
    with pytest.raises(ValueError):
        store.claim_due(now=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError):
        store.claim_due(now=NOW, lease_seconds=0)
