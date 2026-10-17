"""Review endpoint auth, actor binding and tenant isolation contracts."""
from datetime import datetime, timezone
from uuid import uuid4

from rkjo_api.jwt_auth import create_access_token
from rkjo_api.lexia_review import get_legal_review_inbox
from rkjo_api.main import app
from rkjo_api.security import ApiRole
from rkjo_kernel.rag.postgres_legal_review import ReviewEvent


def token(role, tenant="cabinet-a", subject="juriste-1"):
    return {"Authorization": "Bearer " + create_access_token(
        subject=subject, role=role, tenant_id=tenant,
    )}


class MemoryReviewInbox:
    def __init__(self, packet_id):
        self.packet_id = packet_id
        self.calls = []
        self.events = [ReviewEvent(
            packet_id=packet_id, tenant_id="cabinet-a",
            actor_id="system", action="submitted", note="",
            occurred_at=datetime.now(timezone.utc),
        )]

    def list_review_events(self, *, packet_id, tenant_id):
        self.calls.append(("list", tenant_id))
        if packet_id != self.packet_id or tenant_id != "cabinet-a":
            return []
        return list(self.events)

    def append_review_event(self, *, packet_id, tenant_id, actor_id, action, note):
        self.calls.append(("append", tenant_id, actor_id, action, note))
        if packet_id != self.packet_id or tenant_id != "cabinet-a":
            return False
        self.events.append(ReviewEvent(
            packet_id=packet_id, tenant_id=tenant_id, actor_id=actor_id,
            action=action, note=note, occurred_at=datetime.now(timezone.utc),
        ))
        return True


def test_operator_can_record_event_using_authenticated_subject(client):
    packet_id = uuid4()
    repository = MemoryReviewInbox(packet_id)
    app.dependency_overrides[get_legal_review_inbox] = lambda: repository
    try:
        response = client.post(
            f"/rag/lexia/review/{packet_id}/events",
            headers=token(ApiRole.OPERATOR),
            json={"action": "review_note", "note": "Contrôle en cours"},
        )
        assert response.status_code == 201, response.text
        assert repository.calls[-1] == (
            "append", "cabinet-a", "juriste-1", "review_note", "Contrôle en cours"
        )
        events = client.get(
            f"/rag/lexia/review/{packet_id}/events",
            headers=token(ApiRole.OPERATOR),
        )
        assert events.status_code == 200
        assert len(events.json()) == 2
    finally:
        app.dependency_overrides.pop(get_legal_review_inbox, None)


def test_viewer_cannot_review_or_list(client):
    packet_id = uuid4()
    repo = MemoryReviewInbox(packet_id)
    app.dependency_overrides[get_legal_review_inbox] = lambda: repo
    try:
        assert client.get(
            f"/rag/lexia/review/{packet_id}/events",
            headers=token(ApiRole.VIEWER),
        ).status_code == 403
        assert client.post(
            f"/rag/lexia/review/{packet_id}/events",
            headers=token(ApiRole.VIEWER),
            json={"action": "review_note", "note": "Non"},
        ).status_code == 403
        assert repo.calls == []
    finally:
        app.dependency_overrides.pop(get_legal_review_inbox, None)


def test_cross_tenant_is_indistinguishable_from_missing(client):
    packet_id = uuid4()
    repo = MemoryReviewInbox(packet_id)
    app.dependency_overrides[get_legal_review_inbox] = lambda: repo
    try:
        assert client.get(
            f"/rag/lexia/review/{packet_id}/events",
            headers=token(ApiRole.ADMIN, tenant="cabinet-b"),
        ).status_code == 404
        assert client.post(
            f"/rag/lexia/review/{packet_id}/events",
            headers=token(ApiRole.ADMIN, tenant="cabinet-b"),
            json={"action": "rejected", "note": "Tentative interdite"},
        ).status_code == 404
        assert len(repo.events) == 1
    finally:
        app.dependency_overrides.pop(get_legal_review_inbox, None)


def test_key_without_personal_identity_is_refused(client):
    packet_id = uuid4()
    repo = MemoryReviewInbox(packet_id)
    app.dependency_overrides[get_legal_review_inbox] = lambda: repo
    try:
        result = client.post(
            f"/rag/lexia/review/{packet_id}/events",
            headers={"X-API-Key": "rkjo-operator-key"},
            json={"action": "review_note", "note": "Essai"},
        )
        assert result.status_code == 403
        assert repo.calls == []
    finally:
        app.dependency_overrides.pop(get_legal_review_inbox, None)


def test_no_self_approval_and_no_unbound_identity(client):
    packet_id = uuid4()
    repo = MemoryReviewInbox(packet_id)
    app.dependency_overrides[get_legal_review_inbox] = lambda: repo
    try:
        invalid = client.post(
            f"/rag/lexia/review/{packet_id}/events",
            headers=token(ApiRole.ADMIN),
            json={"action": "approved", "note": "Approuver directement"},
        )
        assert invalid.status_code == 422
        unbound = client.post(
            f"/rag/lexia/review/{packet_id}/events",
            headers=token(ApiRole.ADMIN, tenant=None),
            json={"action": "review_note", "note": "Essai"},
        )
        assert unbound.status_code == 403
        assert repo.calls == []
    finally:
        app.dependency_overrides.pop(get_legal_review_inbox, None)
