import pytest
from rkjo_kernel.security.configuration import authority_from_env
from rkjo_kernel.security.authority import PostgreSQLSecurityAuthority


def test_distributed_profile_cannot_silently_fall_back(monkeypatch):
    monkeypatch.setenv('RKJO_SECURITY_PROFILE','distributed')
    monkeypatch.delenv('RKJO_SECURITY_AUTHORITY_DATABASE_URL',raising=False)
    with pytest.raises(RuntimeError,match='explicit authority'): authority_from_env()
    monkeypatch.setenv('RKJO_SECURITY_AUTHORITY_DATABASE_URL','postgresql://dedicated-test.invalid/test')
    assert isinstance(authority_from_env(),PostgreSQLSecurityAuthority)
    monkeypatch.setenv('RKJO_SECURITY_PROFILE','local')
    with pytest.raises(RuntimeError,match='without distributed'): authority_from_env()
    monkeypatch.delenv('RKJO_SECURITY_AUTHORITY_DATABASE_URL')
    assert authority_from_env() is None
    monkeypatch.setenv('RKJO_SECURITY_PROFILE','typo')
    with pytest.raises(RuntimeError,match='must be local or distributed'): authority_from_env()
