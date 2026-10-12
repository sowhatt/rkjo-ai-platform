"""Security and admission tests for P0.2 local-only staging."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from rkjo_api.education_study_audio_staging import _identity_and_gate
from rkjo_api.security import ApiRole, required_role_for_request
from rkjo_education.curriculum.study_audio_postgres import PostgresStudyAudioStaging


def request(host="127.0.0.1", tenant="tenant-a", learner="student-a", bearer=True):
    return SimpleNamespace(
        client=SimpleNamespace(host=host),
        state=SimpleNamespace(api_tenant_id=tenant, api_subject=learner),
        headers={"authorization": "Bearer test"} if bearer else {},
    )


def test_staging_disabled_by_default(monkeypatch):
    monkeypatch.delenv("RKJO_EDUCATION_AUDIO_STAGING", raising=False)
    monkeypatch.delenv("RKJO_AUDIO_STORAGE_ACK", raising=False)
    with pytest.raises(HTTPException) as error:
        _identity_and_gate(request())
    assert error.value.status_code == 404


def test_only_loopback_allowed(monkeypatch):
    monkeypatch.setenv("RKJO_EDUCATION_AUDIO_STAGING", "enabled")
    monkeypatch.setenv("RKJO_AUDIO_STORAGE_ACK", "local-postgres-only")
    with pytest.raises(HTTPException) as error:
        _identity_and_gate(request(host="10.1.2.3"))
    assert error.value.status_code == 404


def test_tenant_bound_bearer_required(monkeypatch):
    monkeypatch.setenv("RKJO_EDUCATION_AUDIO_STAGING", "enabled")
    monkeypatch.setenv("RKJO_AUDIO_STORAGE_ACK", "local-postgres-only")
    for test_request in (request(tenant=None), request(learner=None), request(bearer=False)):
        with pytest.raises(HTTPException) as error:
            _identity_and_gate(test_request)
        assert error.value.status_code == 403
    assert _identity_and_gate(request()) == ("tenant-a", "student-a")


def test_student_minimal_permissions():
    assert required_role_for_request(method="POST", path="/education/study/stage-audio") is ApiRole.VIEWER
    assert required_role_for_request(method="GET", path="/education/study/staged-audio/id") is ApiRole.VIEWER
    assert required_role_for_request(method="DELETE", path="/education/study/staged-audio/id") is ApiRole.VIEWER
    assert required_role_for_request(method="POST", path="/education/courses") is ApiRole.OPERATOR


def test_repository_requires_database():
    with pytest.raises(ValueError):
        PostgresStudyAudioStaging("")
