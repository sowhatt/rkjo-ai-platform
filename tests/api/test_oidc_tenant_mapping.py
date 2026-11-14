"""Mapping contracts only; mocked verified claims are NOT real-IdP evidence."""
import hashlib
import pytest
import jwt
from rkjo_api import oidc_auth
from rkjo_api.security import ApiRole


@pytest.fixture
def claims(monkeypatch):
    payload = {"sub":"user-a","role":"operator","iss":"https://issuer.test","organization":"external-a"}
    monkeypatch.setenv("RKJO_OIDC_TENANT_CLAIM","organization")
    monkeypatch.setenv("RKJO_OIDC_TENANT_MAP",'{"external-a":"tenant-a","external-b":"tenant-b"}')
    monkeypatch.setattr(oidc_auth,"decode_oidc_token",lambda token:dict(payload))
    return payload


def test_verified_claim_is_allowlisted_and_principal_namespaced(claims):
    user, role, tenant = oidc_auth.resolve_oidc_identity_with_tenant("mock-verified-token")
    assert (user,role,tenant) == ("oidc:"+hashlib.sha256(b"https://issuer.test").hexdigest()+":user-a",ApiRole.OPERATOR,"tenant-a")


@pytest.mark.parametrize("value",[None,"foreign",["external-a"]," external-a"])
def test_missing_foreign_or_malformed_claim_is_rejected(claims,value):
    claims["organization"] = value
    with pytest.raises(jwt.InvalidTokenError): oidc_auth.resolve_oidc_identity_with_tenant("mock-verified-token")


def test_conflicting_signed_claim_is_rejected(claims):
    claims["tenant_id"] = "tenant-b"
    with pytest.raises(jwt.InvalidTokenError): oidc_auth.resolve_oidc_identity_with_tenant("mock-verified-token")


@pytest.mark.parametrize("mapping",["", "[]", "{}", "invalid", '{"external-a":""}'])
def test_absent_or_invalid_mapping_never_infers_a_tenant(claims,monkeypatch,mapping):
    monkeypatch.setenv("RKJO_OIDC_TENANT_MAP",mapping)
    with pytest.raises(RuntimeError): oidc_auth.resolve_oidc_identity_with_tenant("mock-verified-token")
