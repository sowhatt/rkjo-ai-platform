"""Family API onboarding tests."""

from __future__ import annotations

from starlette.requests import Request

from rkjo_api.family import (
    HouseholdCreateRequest,
    HouseholdMemberCreateRequest,
    add_household_member,
    create_household,
    list_households,
)
from rkjo_family.household.models import HouseholdRole
from rkjo_family.household.repository import InMemoryHouseholdRepository
from rkjo_family.household.service import HouseholdService


def _request(*, tenant_id: str) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/family/households",
        "headers": [],
        "state": {
            "api_role": "admin",
            "api_subject": "user-1",
            "api_tenant_id": tenant_id,
        },
    }
    return Request(scope)


def test_create_household_binds_authenticated_tenant():
    service = HouseholdService(InMemoryHouseholdRepository())

    response = create_household(
        HouseholdCreateRequest(
            household_id="home-1",
            name="Famille Test",
            admin_member_id="parent-1",
            admin_display_name="Parent",
        ),
        _request(tenant_id="tenant-a"),
        service,
    )

    stored = service.get(tenant_id="tenant-a", household_id="home-1")
    assert response.household_id == "home-1"
    assert stored.tenant_id == "tenant-a"
    assert stored.members[0].permissions == frozenset({"family.management"})


def test_household_listing_is_tenant_scoped():
    repository = InMemoryHouseholdRepository()
    service = HouseholdService(repository)

    create_household(
        HouseholdCreateRequest(
            household_id="home-a",
            name="Famille A",
            admin_member_id="parent-a",
            admin_display_name="Parent A",
        ),
        _request(tenant_id="tenant-a"),
        service,
    )
    create_household(
        HouseholdCreateRequest(
            household_id="home-b",
            name="Famille B",
            admin_member_id="parent-b",
            admin_display_name="Parent B",
        ),
        _request(tenant_id="tenant-b"),
        service,
    )

    response = list_households(_request(tenant_id="tenant-a"), service)
    assert [item.household_id for item in response] == ["home-a"]


def test_add_member_uses_authenticated_tenant():
    service = HouseholdService(InMemoryHouseholdRepository())
    request = _request(tenant_id="tenant-a")

    create_household(
        HouseholdCreateRequest(
            household_id="home-1",
            name="Famille Test",
            admin_member_id="parent-1",
            admin_display_name="Parent",
        ),
        request,
        service,
    )

    response = add_household_member(
        "home-1",
        HouseholdMemberCreateRequest(
            member_id="child-1",
            display_name="Enfant",
            role=HouseholdRole.CHILD,
            permissions=["education.tutoring"],
        ),
        request,
        service,
    )

    assert len(response.members) == 2
    assert response.members[1].role is HouseholdRole.CHILD
