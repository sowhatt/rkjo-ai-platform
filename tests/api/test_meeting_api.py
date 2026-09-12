import uuid

import pytest
from fastapi.testclient import TestClient

from rkjo_api.main import app
from rkjo_api.meeting import get_meeting_repository
from rkjo_meeting_intelligence.infrastructure.memory_repository import InMemoryMeetingRepository


client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_meeting_repository():
    repository = InMemoryMeetingRepository()
    app.dependency_overrides[get_meeting_repository] = lambda: repository
    yield repository
    app.dependency_overrides.pop(get_meeting_repository, None)


def _operator(monkeypatch, tenant_id: str):
    key = f"operator-{uuid.uuid4().hex}"
    monkeypatch.setenv("RKJO_OPERATOR_API_KEY", key)
    monkeypatch.setenv("RKJO_OPERATOR_TENANT_ID", tenant_id)
    return {"X-API-Key": key}


def test_meetings_require_authentication(monkeypatch):
    monkeypatch.setenv("RKJO_VIEWER_API_KEY", "viewer-meeting-key")
    monkeypatch.setenv("RKJO_VIEWER_TENANT_ID", "meeting-tenant-auth")
    assert client.get("/meetings").status_code == 401


def test_viewer_cannot_create_meeting(monkeypatch):
    monkeypatch.setenv("RKJO_VIEWER_API_KEY", "viewer-meeting-key")
    monkeypatch.setenv("RKJO_VIEWER_TENANT_ID", "meeting-tenant-viewer")
    response = client.post(
        "/meetings",
        headers={"X-API-Key": "viewer-meeting-key"},
        json={"title": "Comite strategique"},
    )
    assert response.status_code == 403


def test_operator_can_create_then_read_meeting(monkeypatch):
    headers = _operator(monkeypatch, "meeting-tenant-read")
    created = client.post("/meetings", headers=headers, json={"title": "Projet RKJO"})
    assert created.status_code == 201
    meeting_id = created.json()["meeting_id"]
    response = client.get(f"/meetings/{meeting_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["meeting_id"] == meeting_id


def test_cross_tenant_read_returns_404(monkeypatch):
    headers_a = _operator(monkeypatch, "meeting-api-tenant-a")
    created = client.post("/meetings", headers=headers_a, json={"title": "Tenant A"})
    meeting_id = created.json()["meeting_id"]
    headers_b = _operator(monkeypatch, "meeting-api-tenant-b")
    assert client.get(f"/meetings/{meeting_id}", headers=headers_b).status_code == 404


def test_operator_can_list_tenant_meetings(monkeypatch):
    headers = _operator(monkeypatch, "meeting-tenant-list")
    created = client.post("/meetings", headers=headers, json={"title": "A lister"})
    meeting_id = created.json()["meeting_id"]
    response = client.get("/meetings", headers=headers)
    assert response.status_code == 200
    assert meeting_id in {item["meeting_id"] for item in response.json()}


def test_full_meeting_workflow_api(monkeypatch):
    headers = _operator(monkeypatch, "meeting-tenant-workflow")
    created = client.post("/meetings", headers=headers, json={"title": "CODIR"})
    assert created.status_code == 201
    meeting_id = created.json()["meeting_id"]

    participant = client.post(
        f"/meetings/{meeting_id}/participants",
        headers=headers,
        json={"display_name": "Alice", "role": "DG", "email": "alice@example.com"},
    )
    assert participant.status_code == 201
    participant_id = participant.json()["participant_id"]

    segment = client.post(
        f"/meetings/{meeting_id}/transcript",
        headers=headers,
        json={
            "text": "Nous validons le lancement.",
            "start_seconds": 12.0,
            "end_seconds": 16.0,
            "speaker_id": participant_id,
            "confidence": 0.99,
        },
    )
    assert segment.status_code == 201
    segment_id = segment.json()["segment_id"]

    decision = client.post(
        f"/meetings/{meeting_id}/decisions",
        headers=headers,
        json={"text": "Lancement valide", "source_segment_id": segment_id},
    )
    assert decision.status_code == 201

    action = client.post(
        f"/meetings/{meeting_id}/actions",
        headers=headers,
        json={
            "title": "Preparer le lancement",
            "source_segment_id": segment_id,
            "assignee_id": participant_id,
        },
    )
    assert action.status_code == 201

    assert client.get(f"/meetings/{meeting_id}/participants", headers=headers).status_code == 200
    assert client.get(f"/meetings/{meeting_id}/transcript", headers=headers).status_code == 200
    assert client.get(f"/meetings/{meeting_id}/decisions", headers=headers).status_code == 200
    assert client.get(f"/meetings/{meeting_id}/actions", headers=headers).status_code == 200
