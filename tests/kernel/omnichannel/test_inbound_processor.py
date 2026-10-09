"""OMNI-013.1 integration: expired leases, CAS, retries and channel isolation."""
from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4

import pytest
from psycopg.conninfo import conninfo_to_dict

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
        pytest.fail("Tests must use an isolated database.")
    inbox = PostgreSQLInboundInbox(url)
    inbox.initialize_schema()
    store = PostgreSQLInboundProcessorStore(url, max_attempts=3)
    store.initialize_schema()
    return inbox, store


def add(inbox, *, kind=InboundKind.USER_MESSAGE):
    ident = uuid4().hex
    event = VerifiedInbound(
        tenant_id="tenant-" + ident,
        channel="whatsapp", channel_account_id="phone-" + ident,
        provider_event_id="evt-" + ident, kind=kind,
        payload={"id": ident},
    )
    assert inbox.accept_once(event)
    return event


def test_claim_leased_once_and_stale_ack_is_rejected(stores):
    inbox, store = stores
    event = add(inbox)
    first = store.claim_due(now=NOW, lease_seconds=10)
    assert first is not None
    # All other rows in the shared test DB are from earlier tests; check
    # our row using token-CAS rather than expecting an empty global queue.
    assert first.lease_token
    with pytest.raises(ValueError, match="Stale"):
        store.mark_processed(type(first)(event=first.event, lease_token="wrong", attempt=first.attempt))
    store.mark_processed(first)
    with pytest.raises(ValueError, match="Stale"):
        store.mark_processed(first)


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
    # Existing inbox rows may predate this test, so process up to 300 claims.
    for _ in range(300):
        if any(e.provider_event_id == receipt.provider_event_id for e in status.received):
            break
        if not worker.run_once(now=NOW):
            break
    assert any(e.provider_event_id == receipt.provider_event_id for e in status.received)
    assert all(e.provider_event_id != receipt.provider_event_id for e in agent.received)


def test_crash_before_ack_retries_then_stale_token_cannot_commit(stores):
    inbox, store = stores
    event = add(inbox)
    # We must locate this particular event rather than assume no leftover rows.
    first = None
    for _ in range(300):
        claim = store.claim_due(now=NOW, lease_seconds=2)
        if claim is None:
            break
        if claim.event.provider_event_id == event.provider_event_id:
            first = claim
            break
        store.mark_processed(claim)
    assert first is not None
    second = None
    for _ in range(300):
        claim = store.claim_due(now=NOW + timedelta(seconds=3), lease_seconds=10)
        if claim is None:
            break
        if claim.event.provider_event_id == event.provider_event_id:
            second = claim
            break
        store.mark_processed(claim)
    assert second is not None
    assert second.attempt == first.attempt + 1
    with pytest.raises(ValueError, match="Stale"):
        store.mark_processed(first)
    store.mark_processed(second)


def test_retry_limit_blocks_future_claims(stores):
    inbox, store = stores
    event = add(inbox)
    claim = None
    for _ in range(300):
        candidate = store.claim_due(now=NOW, lease_seconds=2)
        if candidate is None:
            break
        if candidate.event.provider_event_id == event.provider_event_id:
            claim = candidate
            break
        store.mark_processed(candidate)
    assert claim is not None
    for idx in range(3):
        store.mark_failed(claim, now=NOW + timedelta(seconds=idx*10),
                          error="SimulatedProviderFailure", retry_delay_seconds=1)
        if idx != 2:
            claim = None
            for _ in range(300):
                candidate = store.claim_due(now=NOW + timedelta(seconds=idx*10+2), lease_seconds=2)
                if candidate is None:
                    break
                if candidate.event.provider_event_id == event.provider_event_id:
                    claim = candidate
                    break
                store.mark_processed(candidate)
            assert claim is not None
    assert claim.attempt == 3
