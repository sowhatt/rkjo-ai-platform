"""Explicit local/distributed profiles; no silent downgrade on misconfiguration."""
import os
from .authority import PostgreSQLSecurityAuthority


def authority_from_env():
    profile = os.getenv("RKJO_SECURITY_PROFILE", "local").strip()
    dsn = os.getenv("RKJO_SECURITY_AUTHORITY_DATABASE_URL", "").strip()
    if profile not in {"local", "distributed"}:
        raise RuntimeError("RKJO_SECURITY_PROFILE must be local or distributed.")
    if profile == "local":
        if dsn:
            raise RuntimeError("Authority configured without distributed profile.")
        return None
    if not dsn:
        raise RuntimeError("Distributed profile requires an explicit authority database URL.")
    return PostgreSQLSecurityAuthority(dsn)
