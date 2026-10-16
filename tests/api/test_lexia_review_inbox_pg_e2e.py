"""Opt-in real PostgreSQL quarantine audit and tenant isolation tests."""
from __future__ import annotations

import hashlib
import os
from datetime import date
from uuid import uuid4

import pytest

from rkjo_kernel.rag.legal_intake import prepare_legal_intake
from rkjo_kernel.rag.postgres_legal_review import PostgresLegalReviewInbox


@pytest.mark.integration
def test_review_inbox_is_persistent_private_and_never_publishes():
    url = os.getenv("RKJO_LEXIA_TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("Disposable RKJO_LEXIA_TEST_DATABASE_URL required")

    prefix = "lexia_review_e2e_" + uuid4().hex[:12]
    inbox = PostgresLegalReviewInbox(database_url=url, table_prefix=prefix)
    document = "Imaginary Bénin legal source, not legally verified".encode("utf-8")
    digest = hashlib.sha256(document).hexdigest()
    packet = prepare_legal_intake(
        document=document,
        authenticated_tenant_id="cabinet-a",
        on_date=date(2026, 10, 16),
        metadata={
            "country": "BJ", "domain": "droit",
            "canonical_id": "FAKE:1", "title": "Document test",
            "article": "X", "source": "fixture",
            "official_source_url": "https://example.org/fiction",
            "checksum_sha256": digest, "effective_from": "2020-01-01",
            "status": "IN_FORCE",
        },
    )
    assert packet.state == "awaiting_human_review"
    assert not packet.can_index_as_verified

    created = False
    try:
        inbox.initialize_schema()
        created = True
        packet_id = inbox.submit(packet=packet, tenant_id="cabinet-a", actor_id="reviewer-1")
        assert inbox.append_review_event(
            packet_id=packet_id, tenant_id="cabinet-a", actor_id="reviewer-1",
            action="review_requested", note="Vérifier la source officielle",
        )
        # New repository instance checks that records really persist.
        reloaded = PostgresLegalReviewInbox(database_url=url, table_prefix=prefix)
        events = reloaded.list_review_events(packet_id=packet_id, tenant_id="cabinet-a")
        assert [event.action for event in events] == ["submitted", "review_requested"]
        assert events[1].actor_id == "reviewer-1"

        # Cross-tenant read and write are indistinguishable from missing records.
        assert reloaded.list_review_events(packet_id=packet_id, tenant_id="cabinet-b") == []
        assert not reloaded.append_review_event(
            packet_id=packet_id, tenant_id="cabinet-b", actor_id="reviewer-2",
            action="review_note", note="Cross tenant",
        )
        with pytest.raises(PermissionError):
            inbox.submit(packet=packet, tenant_id="cabinet-b", actor_id="reviewer-2")

        # Even a reviewer cannot mark verified or publish through this repository.
        with pytest.raises(ValueError):
            inbox.append_review_event(
                packet_id=packet_id, tenant_id="cabinet-a", actor_id="reviewer-1",
                action="approved", note="Do not auto-publish",
            )
        with pytest.raises(ValueError):
            inbox.append_review_event(
                packet_id=packet_id, tenant_id="cabinet-a", actor_id="reviewer-1",
                action="review_note", note="",
            )
        assert len(inbox.list_review_events(packet_id=packet_id, tenant_id="cabinet-a")) == 2
    finally:
        if created:
            inbox.drop_schema()
