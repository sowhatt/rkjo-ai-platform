"""Fail-closed PWA integration contract until per-learner sessions are available.

This static contract test complements (but cannot replace) browser security
tests. It specifically prevents a future accidental operator-key fallback.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "apps/web/src/app/api/education/attempts/[attemptId]/questions/[questionId]/next-action/route.ts"


def test_proxy_does_not_forward_shared_pilot_as_student():
    source = ROUTE.read_text(encoding="utf-8")
    assert 'readPilotSession(request)' in source
    assert 'status: 401' in source
    assert 'status: 403' in source
    assert 'Cache-Control' in source
    assert 'RKJO_OPERATOR_API_KEY' not in source
    assert 'X-API-Key' not in source
    assert 'backendPilotBearer(' not in source


def test_proxy_has_no_unverified_learner_override():
    source = ROUTE.read_text(encoding="utf-8")
    assert 'searchParams.get("learnerId")' not in source
    assert 'request.nextUrl.searchParams' not in source
    assert 'fetch(' not in source
