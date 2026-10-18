"""JWT four-eyes endpoint contracts; never trust user-supplied actor or tenant."""
from uuid import uuid4

from rkjo_api.jwt_auth import create_access_token
from rkjo_api.lexia_review import get_legal_four_eyes_workflow
from rkjo_api.main import app
from rkjo_api.security import ApiRole
from rkjo_kernel.rag.legal_four_eyes import FourEyesResult


def auth(role=ApiRole.OPERATOR, tenant="cabinet-a", subject="juriste-a"):
    return {"Authorization": "Bearer " + create_access_token(
        subject=subject, role=role, tenant_id=tenant,
    )}


class FakeWorkflow:
    def __init__(self, packet):
        self.packet = packet
        self.calls = []

    def verify(self, *, packet_id, tenant_id, dossier_id, actor_id, note):
        self.calls.append((packet_id, tenant_id, dossier_id, actor_id, note))
        if packet_id != self.packet or tenant_id != "cabinet-a":
            return None
        if dossier_id != "case-a" or actor_id == "blocked":
            raise PermissionError("not authorized")
        return FourEyesResult(state="awaiting_second_review", reviewer_count=1)


def test_jwt_subject_and_tenant_are_bound(client):
    packet = uuid4()
    service = FakeWorkflow(packet)
    app.dependency_overrides[get_legal_four_eyes_workflow] = lambda: service
    try:
        result = client.post(
            f"/rag/lexia/review/{packet}/verify",
            headers=auth(subject="juriste-a"),
            json={"dossier_id": "case-a", "note": "Source examinée"},
        )
        assert result.status_code == 200, result.text
        assert result.json() == {
            "state": "awaiting_second_review",
            "reviewer_count": 1,
            "publishable": False,
        }
        assert service.calls == [
            (packet, "cabinet-a", "case-a", "juriste-a", "Source examinée")
        ]
    finally:
        app.dependency_overrides.pop(get_legal_four_eyes_workflow, None)


def test_viewer_and_anonymous_api_key_are_forbidden(client):
    packet = uuid4()
    service = FakeWorkflow(packet)
    app.dependency_overrides[get_legal_four_eyes_workflow] = lambda: service
    try:
        path = f"/rag/lexia/review/{packet}/verify"
        data = {"dossier_id": "case-a", "note": "Attempt"}
        assert client.post(path, headers=auth(role=ApiRole.VIEWER),
                           json=data).status_code == 403
        assert client.post(path, headers={"X-API-Key": "rkjo-operator-key"},
                           json=data).status_code == 403
        assert service.calls == []
    finally:
        app.dependency_overrides.pop(get_legal_four_eyes_workflow, None)


def test_cross_tenant_and_wrong_dossier_refused(client):
    packet = uuid4()
    service = FakeWorkflow(packet)
    app.dependency_overrides[get_legal_four_eyes_workflow] = lambda: service
    try:
        path = f"/rag/lexia/review/{packet}/verify"
        assert client.post(path, headers=auth(tenant="cabinet-b"),
                           json={"dossier_id": "case-a", "note": "Attempt"}).status_code == 404
        assert client.post(path, headers=auth(),
                           json={"dossier_id": "case-b", "note": "Attempt"}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_legal_four_eyes_workflow, None)


def test_cannot_override_actor_or_publish(client):
    packet = uuid4()
    service = FakeWorkflow(packet)
    app.dependency_overrides[get_legal_four_eyes_workflow] = lambda: service
    try:
        response = client.post(
            f"/rag/lexia/review/{packet}/verify",
            headers=auth(),
            json={"dossier_id": "case-a", "note": "Review",
                  "tenant_id": "cabinet-b", "actor_id": "other", "publishable": True},
        )
        assert response.status_code == 200
        assert response.json()["publishable"] is False
        assert service.calls[0][1:4] == ("cabinet-a", "case-a", "juriste-a")
        missing = client.post(
            f"/rag/lexia/review/{packet}/verify",
            headers=auth(tenant=None),
            json={"dossier_id": "case-a", "note": "Review"},
        )
        assert missing.status_code == 403
    finally:
        app.dependency_overrides.pop(get_legal_four_eyes_workflow, None)
