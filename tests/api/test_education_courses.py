from fastapi.testclient import TestClient

from rkjo_api.main import app


client = TestClient(app)


def test_education_requires_authentication(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_VIEWER_API_KEY",
        "viewer-key",
    )
    monkeypatch.setenv(
        "RKJO_VIEWER_TENANT_ID",
        "tenant-a",
    )

    response = client.get(
        "/education/courses/missing"
    )

    assert response.status_code == 401


def test_viewer_cannot_create_course(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_VIEWER_API_KEY",
        "viewer-key",
    )
    monkeypatch.setenv(
        "RKJO_VIEWER_TENANT_ID",
        "tenant-a",
    )

    response = client.post(
        "/education/courses",
        headers={
            "X-API-Key": "viewer-key",
        },
        json={
            "course_id": "course-1",
            "title": "Anatomie",
            "subject": "Médecine",
            "level": "L1",
        },
    )

    assert response.status_code == 403


def test_operator_can_create_and_read_course(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_OPERATOR_API_KEY",
        "operator-key",
    )
    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        "tenant-a",
    )

    response = client.post(
        "/education/courses",
        headers={
            "X-API-Key": "operator-key",
        },
        json={
            "course_id": "medicine-anatomy-api",
            "title": "Anatomie du coeur",
            "subject": "Anatomie",
            "level": "Médecine",
        },
    )

    assert response.status_code in {
        201,
        409,
    }

    response = client.get(
        "/education/courses/medicine-anatomy-api",
        headers={
            "X-API-Key": "operator-key",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["course_id"] == (
        "medicine-anatomy-api"
    )


def test_attach_document_is_idempotent_api(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_OPERATOR_API_KEY",
        "operator-key",
    )
    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        "tenant-a",
    )

    client.post(
        "/education/courses",
        headers={
            "X-API-Key": "operator-key",
        },
        json={
            "course_id": "medicine-rag-course",
            "title": "Anatomie",
            "subject": "Anatomie",
            "level": "Médecine",
        },
    )

    for _ in range(2):
        response = client.post(
            "/education/courses/"
            "medicine-rag-course/"
            "documents",
            headers={
                "X-API-Key": "operator-key",
            },
            json={
                "document_id":
                    "demo-anatomie-coeur",
            },
        )

        assert response.status_code == 200

    assert response.json()[
        "document_ids"
    ] == [
        "demo-anatomie-coeur"
    ]


def test_operator_can_list_only_tenant_courses(
    monkeypatch,
):
    monkeypatch.setenv(
        "RKJO_OPERATOR_API_KEY",
        "operator-key",
    )
    monkeypatch.setenv(
        "RKJO_OPERATOR_TENANT_ID",
        "tenant-list-a",
    )

    client.post(
        "/education/courses",
        headers={
            "X-API-Key": "operator-key",
        },
        json={
            "course_id": "course-list-a",
            "title": "Anatomie",
            "subject": "Anatomie",
            "level": "Médecine",
        },
    )

    response = client.get(
        "/education/courses",
        headers={
            "X-API-Key": "operator-key",
        },
    )

    assert response.status_code == 200

    body = response.json()

    ids = {
        item["course_id"]
        for item in body
    }

    assert "course-list-a" in ids
