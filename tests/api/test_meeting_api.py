from fastapi.testclient import TestClient

from rkjo_api.main import app


client = TestClient(app)


def test_meetings_require_authentication(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_VIEWER_API_KEY",
        "viewer-meeting-key",
    )
    monkeypatch.setenv(
        "RKJO_VIEWER_TENANT_ID",
        "meeting-tenant-auth",
    )

    response = client.get(
        "/meetings"
    )

    assert response.status_code == 401


def test_viewer_cannot_create_meeting(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_VIEWER_API_KEY",
        "viewer-meeting-key",
    )
    monkeypatch.setenv(
        "RKJO_VIEWER_TENANT_ID",
        "meeting-tenant-viewer",
    )

    response = client.post(
        "/meetings",
        headers={
            "X-API-Key":
                "viewer-meeting-key",
        },
        json={
            "title":
                "Comité stratégique",
        },
    )

    assert response.status_code == 403


def test_operator_can_create_meeting(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_OPERATOR_API_KEY",
        "operator-meeting-key",
    )
    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        "meeting-tenant-create",
    )

    response = client.post(
        "/meetings",
        headers={
            "X-API-Key":
                "operator-meeting-key",
        },
        json={
            "title":
                "Comité de direction",
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert (
        body["title"]
        == "Comité de direction"
    )
    assert body["meeting_id"]
    assert body["status"] == "draft"


def test_operator_can_create_then_read_meeting(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_OPERATOR_API_KEY",
        "operator-read-key",
    )
    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        "meeting-tenant-read",
    )

    headers = {
        "X-API-Key":
            "operator-read-key",
    }

    created = client.post(
        "/meetings",
        headers=headers,
        json={
            "title":
                "Réunion projet RKJO",
        },
    )

    assert created.status_code == 201

    meeting_id = (
        created.json()["meeting_id"]
    )

    response = client.get(
        f"/meetings/{meeting_id}",
        headers=headers,
    )

    assert response.status_code == 200

    assert (
        response.json()["meeting_id"]
        == meeting_id
    )


def test_list_meetings_is_tenant_scoped(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_OPERATOR_API_KEY",
        "tenant-a-key",
    )
    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        "meeting-api-tenant-a",
    )

    response = client.post(
        "/meetings",
        headers={
            "X-API-Key":
                "tenant-a-key",
        },
        json={
            "title":
                "Réunion privée tenant A",
        },
    )

    assert response.status_code == 201

    meeting_id = (
        response.json()["meeting_id"]
    )

    monkeypatch.setenv(
        "RKJO_OPERATOR_API_KEY",
        "tenant-b-key",
    )
    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        "meeting-api-tenant-b",
    )

    response = client.get(
        f"/meetings/{meeting_id}",
        headers={
            "X-API-Key":
                "tenant-b-key",
        },
    )

    assert response.status_code == 404


def test_operator_can_list_tenant_meetings(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_OPERATOR_API_KEY",
        "list-meeting-key",
    )
    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        "meeting-tenant-list",
    )

    headers = {
        "X-API-Key":
            "list-meeting-key",
    }

    response = client.post(
        "/meetings",
        headers=headers,
        json={
            "title":
                "Réunion à lister",
        },
    )

    assert response.status_code == 201

    meeting_id = (
        response.json()["meeting_id"]
    )

    response = client.get(
        "/meetings",
        headers=headers,
    )

    assert response.status_code == 200

    ids = {
        item["meeting_id"]
        for item in response.json()
    }

    assert meeting_id in ids
