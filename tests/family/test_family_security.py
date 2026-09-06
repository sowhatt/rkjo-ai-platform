"""Security contract for RKJO Family API."""

from rkjo_api.security import (
    ApiRole,
    is_protected_path,
    required_role_for_request,
)


def test_family_routes_are_protected():
    assert is_protected_path("/family")
    assert is_protected_path("/family/households")


def test_family_reads_allow_viewer_and_writes_require_operator():
    assert required_role_for_request(
        method="GET",
        path="/family/households",
    ) is ApiRole.VIEWER

    assert required_role_for_request(
        method="POST",
        path="/family/households",
    ) is ApiRole.OPERATOR
