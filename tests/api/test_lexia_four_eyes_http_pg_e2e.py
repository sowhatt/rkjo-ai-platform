"""Real JWT HTTP -> PostgreSQL four-eyes validation without RAG publication."""
import hashlib
import os
from datetime import date
from uuid import uuid4

import pytest

from rkjo_api.jwt_auth import create_access_token
from rkjo_api.lexia_review import get_legal_four_eyes_workflow
from rkjo_api.main import app
from rkjo_api.security import ApiRole
from rkjo_kernel.rag.legal_four_eyes import LegalFourEyesWorkflow
from rkjo_kernel.rag.legal_intake import prepare_legal_intake
from rkjo_kernel.rag.postgres_legal_review import PostgresLegalReviewInbox


def headers(actor, tenant="cabinet-a"):
    return {"Authorization": "Bearer " + create_access_token(
        subject=actor, role=ApiRole.OPERATOR, tenant_id=tenant,
    )}


@pytest.mark.integration
def test_http_two_reviewers_and_revocation_on_real_database(client):
    url = os.getenv("RKJO_LEXIA_TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("Disposable RKJO_LEXIA_TEST_DATABASE_URL required")
    prefix = "lexia_http_eyes_" + uuid4().hex[:12]
    inbox = PostgresLegalReviewInbox(database_url=url, table_prefix=prefix)
    workflow = LegalFourEyesWorkflow(database_url=url, table_prefix=prefix)
    doc = b"Fictional legal source for end-to-end HTTP verification"
    packet = prepare_legal_intake(
        document=doc, authenticated_tenant_id="cabinet-a", on_date=date(2026, 10, 18),
        metadata={
            "dossier_id": "case-1", "domain": "droit", "country": "BJ",
            "canonical_id": "DEMO:E2E:1", "title": "Fictional",
            "article": "Article fictif", "source": "test",
            "official_source_url": "https://example.org/fake",
            "checksum_sha256": hashlib.sha256(doc).hexdigest(),
            "effective_from": "2020-01-01", "status": "IN_FORCE",
        },
    )
    initialized = workflow_initialized = False
    try:
        inbox.initialize_schema()
        initialized = True
        workflow.initialize_schema()
        workflow_initialized = True
        packet_id = inbox.submit(packet=packet, tenant_id="cabinet-a", actor_id="author")
        for actor in ("first", "second"):
            workflow.grant_reviewer(
                tenant_id="cabinet-a", dossier_id="case-1",
                actor_id=actor, granted_by="admin",
            )
        app.dependency_overrides[get_legal_four_eyes_workflow] = lambda: workflow
        url_path = f"/rag/lexia/review/{packet_id}/verify"
        body = {"dossier_id": "case-1", "note": "Revue humaine du document fictif"}

        assert client.post(url_path, headers=headers("outsider"), json=body).status_code == 403
        assert client.post(url_path, headers=headers("first", "cabinet-b"),
                           json=body).status_code == 404
        first = client.post(url_path, headers=headers("first"), json=body)
        assert first.status_code == 200, first.text
        assert first.json()["reviewer_count"] == 1
        assert first.json()["publishable"] is False
        assert client.post(url_path, headers=headers("first"), json=body).status_code == 403

        assert workflow.revoke_reviewer(
            tenant_id="cabinet-a", dossier_id="case-1",
            actor_id="second", revoked_by="admin",
        )
        assert client.post(url_path, headers=headers("second"), json=body).status_code == 403
        workflow.grant_reviewer(
            tenant_id="cabinet-a", dossier_id="case-1",
            actor_id="second", granted_by="admin",
        )
        second = client.post(url_path, headers=headers("second"), json=body)
        assert second.status_code == 200, second.text
        assert second.json() == {
            "state": "two_reviews_recorded",
            "reviewer_count": 2,
            "publishable": False,
        }
    finally:
        app.dependency_overrides.pop(get_legal_four_eyes_workflow, None)
        if workflow_initialized:
            workflow.drop_schema()
        if initialized:
            inbox.drop_schema()
