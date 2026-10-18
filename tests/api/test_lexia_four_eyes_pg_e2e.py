"""Four-eyes decisions run against a disposable real PostgreSQL database."""
from __future__ import annotations

import hashlib
import os
from datetime import date
from uuid import uuid4

import pytest

from rkjo_kernel.rag.legal_four_eyes import LegalFourEyesWorkflow
from rkjo_kernel.rag.legal_intake import prepare_legal_intake
from rkjo_kernel.rag.postgres_legal_review import PostgresLegalReviewInbox


@pytest.mark.integration
def test_four_eyes_requires_two_different_authorized_reviewers_and_never_publishes():
    url = os.getenv("RKJO_LEXIA_TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("RKJO_LEXIA_TEST_DATABASE_URL must be a disposable database")
    prefix = "lexia_eyes_e2e_" + uuid4().hex[:12]
    inbox = PostgresLegalReviewInbox(database_url=url, table_prefix=prefix)
    workflow = LegalFourEyesWorkflow(database_url=url, table_prefix=prefix)
    document = b"Fictitious legal source for four-eyes testing"
    packet = prepare_legal_intake(
        document=document, authenticated_tenant_id="cabinet-a",
        on_date=date(2026, 10, 16),
        metadata={
            "dossier_id": "dossier-1", "country": "OHADA", "domain": "droit",
            "canonical_id": "FAKE:1", "title": "Fictional", "article": "X",
            "source": "fixture", "official_source_url": "https://example.org/fixture",
            "checksum_sha256": hashlib.sha256(document).hexdigest(),
            "effective_from": "2020-01-01", "status": "IN_FORCE",
        },
    )
    assert packet.state == "awaiting_human_review"
    inbox_ready = workflow_ready = False
    try:
        inbox.initialize_schema()
        inbox_ready = True
        workflow.initialize_schema()
        workflow_ready = True
        packet_id = inbox.submit(
            packet=packet, tenant_id="cabinet-a", actor_id="submitter",
        )
        workflow.grant_reviewer(
            tenant_id="cabinet-a", dossier_id="dossier-1",
            actor_id="juriste-1", granted_by="admin",
        )
        workflow.grant_reviewer(
            tenant_id="cabinet-a", dossier_id="dossier-1",
            actor_id="juriste-2", granted_by="admin",
        )
        workflow.grant_reviewer(
            tenant_id="cabinet-a", dossier_id="dossier-1",
            actor_id="submitter", granted_by="admin",
        )

        with pytest.raises(PermissionError):
            workflow.verify(packet_id=packet_id, tenant_id="cabinet-a",
                            dossier_id="dossier-1", actor_id="submitter", note="My own")
        with pytest.raises(PermissionError):
            workflow.verify(packet_id=packet_id, tenant_id="cabinet-b",
                            dossier_id="dossier-1", actor_id="juriste-1", note="Foreign")
        with pytest.raises(PermissionError):
            workflow.verify(packet_id=packet_id, tenant_id="cabinet-a",
                            dossier_id="dossier-other", actor_id="juriste-1", note="Other")
        with pytest.raises(PermissionError):
            workflow.verify(packet_id=packet_id, tenant_id="cabinet-a",
                            dossier_id="dossier-1", actor_id="outsider", note="No grant")

        first = workflow.verify(packet_id=packet_id, tenant_id="cabinet-a",
                                dossier_id="dossier-1", actor_id="juriste-1",
                                note="First independent review")
        assert first.state == "awaiting_second_review"
        assert first.reviewer_count == 1 and not first.publishable
        with pytest.raises(PermissionError):
            workflow.verify(packet_id=packet_id, tenant_id="cabinet-a",
                            dossier_id="dossier-1", actor_id="juriste-1",
                            note="Double review")

        second = workflow.verify(packet_id=packet_id, tenant_id="cabinet-a",
                                 dossier_id="dossier-1", actor_id="juriste-2",
                                 note="Second independent review")
        assert second.state == "two_reviews_recorded"
        assert second.reviewer_count == 2 and not second.publishable
        with pytest.raises(PermissionError):
            workflow.verify(packet_id=packet_id, tenant_id="cabinet-a",
                            dossier_id="dossier-1", actor_id="juriste-1",
                            note="Third try")
    finally:
        if workflow_ready:
            workflow.drop_schema()
        if inbox_ready:
            inbox.drop_schema()


@pytest.mark.integration
def test_four_eyes_cannot_verify_quarantined_or_rejected_source():
    url = os.getenv("RKJO_LEXIA_TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("RKJO_LEXIA_TEST_DATABASE_URL must be a disposable database")
    prefix = "lexia_eyes_e2e_" + uuid4().hex[:12]
    inbox = PostgresLegalReviewInbox(database_url=url, table_prefix=prefix)
    workflow = LegalFourEyesWorkflow(database_url=url, table_prefix=prefix)
    data = b"fictional"
    packet = prepare_legal_intake(
        document=data, authenticated_tenant_id="cabinet-a",
        on_date=date(2026, 10, 16), metadata={
            "dossier_id": "case-1", "domain": "droit", "country": "BJ",
            "canonical_id": "FAKE:2", "title": "Fake",
            "article": "X", "source": "fixture",
            "official_source_url": "https://example.org/fake",
            "effective_from": "2020-01-01", "status": "REPEALED",
        },
    )
    assert packet.state == "quarantined"
    inbox_ready = workflow_ready = False
    try:
        inbox.initialize_schema()
        inbox_ready = True
        workflow.initialize_schema()
        workflow_ready = True
        packet_id = inbox.submit(packet=packet, tenant_id="cabinet-a", actor_id="author")
        workflow.grant_reviewer(tenant_id="cabinet-a", dossier_id="case-1",
                                actor_id="juriste", granted_by="admin")
        with pytest.raises(PermissionError):
            workflow.verify(packet_id=packet_id, tenant_id="cabinet-a",
                            dossier_id="case-1", actor_id="juriste", note="Cannot")
    finally:
        if workflow_ready:
            workflow.drop_schema()
        if inbox_ready:
            inbox.drop_schema()
