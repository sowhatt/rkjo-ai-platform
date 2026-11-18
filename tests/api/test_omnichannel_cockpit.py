"""OMNI-016.4 RBAC and tenant boundary tests for cockpit."""
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from rkjo_api.omnichannel import _identity
from rkjo_api.security import ApiRole, is_protected_path, required_role_for_request


def request(*, role="viewer", tenant="tenant-a", subject="operator-1"):
    scope={"type":"http","method":"GET","path":"/omnichannel/dashboard",
           "headers":[]}
    value=Request(scope)
    value.state.api_role=role
    value.state.api_tenant_id=tenant
    value.state.api_subject=subject
    return value


def test_dashboard_is_protected_and_viewer_can_read():
    assert is_protected_path("/omnichannel/dashboard")
    assert required_role_for_request(
        method="GET",path="/omnichannel/dashboard",
    )==ApiRole.VIEWER


def test_acknowledgement_requires_operator():
    assert required_role_for_request(
        method="POST",path="/omnichannel/incidents/OUTBOUND_FAILED/acknowledge",
    )==ApiRole.OPERATOR
    assert required_role_for_request(
        method="DELETE",path="/omnichannel/incidents/OUTBOUND_FAILED",
    )==ApiRole.ADMIN


def test_unbound_identity_rejected_without_tenant_fallback():
    with pytest.raises(HTTPException) as exc:
        _identity(request(tenant=None))
    assert exc.value.status_code==403


def test_bound_identity_is_scoped_to_exact_tenant():
    assert _identity(request(tenant="tenant-a"))==("tenant-a","operator-1")
    assert _identity(request(tenant="tenant-b"))==("tenant-b","operator-1")


def test_unauthenticated_identity_rejected():
    value=Request({"type":"http","method":"GET","path":"/omnichannel/dashboard",
                   "headers":[]})
    with pytest.raises(HTTPException) as exc:
        _identity(value)
    assert exc.value.status_code==401
