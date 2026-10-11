"""Pilot HTTP contract tests; JWT resolver is stubbed, never deployed."""
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from rkjo_api.main import app
from rkjo_api.security import ApiRole


@pytest.fixture
def client(monkeypatch, tmp_path):
    tenant, teacher, learner, intruder = uuid4(), uuid4(), uuid4(), uuid4()
    monkeypatch.setenv("RKJO_EDU_CE1_PILOT_ENABLED", "1")
    monkeypatch.setenv("RKJO_EDU_CE1_PILOT_DB", str(tmp_path / "pilot.sqlite3"))
    monkeypatch.setenv("RKJO_EDU_CE1_PILOT_GRANTS", json.dumps([{
        "tenant_id": str(tenant), "teacher_id": str(teacher), "learner_id": str(learner),
    }]))
    identities = {
        "teacher": (str(teacher), ApiRole.OPERATOR, str(tenant)),
        "learner": (str(learner), ApiRole.VIEWER, str(tenant)),
        "intruder": (str(intruder), ApiRole.OPERATOR, str(tenant)),
        "other-tenant": (str(learner), ApiRole.VIEWER, str(uuid4())),
    }

    def stub_resolver(token):
        if token not in identities:
            raise ValueError("Invalid bearer token")
        return identities[token]

    monkeypatch.setattr("rkjo_api.main.resolve_bearer_identity_with_tenant", stub_resolver)
    with TestClient(app) as http:
        yield http, learner


def auth(actor):
    return {"Authorization": "Bearer " + actor}


def open_session(client):
    http, learner = client
    response = http.post("/education/ce1-sessions", headers=auth("teacher"),
                         json={"learner_id": str(learner)})
    assert response.status_code == 201, response.text
    return response.json()["session_id"]


def test_teacher_pause_blocks_learner_turn_then_resume(client):
    http, _ = client
    session = open_session(client)
    url = f"/education/ce1-sessions/{session}"
    assert http.get(url + "/state", headers=auth("learner")).json()["status"] == "active"
    pause = http.post(url + "/commands", headers=auth("teacher"),
                      json={"command": "pause", "expected_version": 0})
    assert pause.status_code == 200, pause.text
    assert pause.json()["version"] == 1
    assert http.get(url + "/state", headers=auth("learner")).json()["status"] == "paused"
    blocked = http.post(url + "/turns", headers=auth("learner"), json={"expected_version": 1})
    assert blocked.status_code == 423
    resume = http.post(url + "/commands", headers=auth("teacher"),
                       json={"command": "resume", "expected_version": 1})
    assert resume.status_code == 200, resume.text
    accepted = http.post(url + "/turns", headers=auth("learner"),
                         json={"expected_version": 2})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["version"] == 3


def test_student_cannot_issue_teacher_command(client):
    http, _ = client
    session = open_session(client)
    r = http.post(f"/education/ce1-sessions/{session}/commands",
                  headers=auth("learner"),
                  json={"command": "pause", "expected_version": 0})
    assert r.status_code == 403


def test_wrong_teacher_and_cross_tenant_cannot_control_or_read(client):
    http, _ = client
    session = open_session(client)
    url = f"/education/ce1-sessions/{session}"
    assert http.post(url + "/commands", headers=auth("intruder"),
                     json={"command": "pause", "expected_version": 0}).status_code == 403
    assert http.get(url + "/state", headers=auth("other-tenant")).status_code == 403


def test_stale_generation_is_rejected(client):
    http, _ = client
    session = open_session(client)
    url = f"/education/ce1-sessions/{session}"
    assert http.post(url + "/turns", headers=auth("learner"),
                     json={"expected_version": 0}).status_code == 200
    assert http.post(url + "/turns", headers=auth("learner"),
                     json={"expected_version": 0}).status_code == 409


def test_fake_api_key_and_missing_auth_fail_closed(client):
    http, _ = client
    response = http.post("/education/ce1-sessions", headers={"X-API-Key": "not-a-token"},
                         json={"learner_id": str(uuid4())})
    assert response.status_code in (401, 403, 503)
    assert http.post("/education/ce1-sessions", json={"learner_id": str(uuid4())}).status_code in (401, 403, 503)


def test_disabled_pilot_rejects_authenticated_call(client, monkeypatch):
    http, learner = client
    monkeypatch.delenv("RKJO_EDU_CE1_PILOT_ENABLED")
    assert http.post("/education/ce1-sessions", headers=auth("teacher"),
                     json={"learner_id": str(learner)}).status_code == 503
