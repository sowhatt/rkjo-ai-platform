import pytest

from rkjo_family.household.models import (
    Household,
    HouseholdMember,
    HouseholdRole,
)
from rkjo_family.household.repository import InMemoryHouseholdRepository
from rkjo_family.household.service import HouseholdService


def make_admin(*, tenant_id: str = "tenant-a", household_id: str = "home-1") -> HouseholdMember:
    return HouseholdMember(
        member_id="parent-1",
        tenant_id=tenant_id,
        household_id=household_id,
        display_name="Parent Admin",
        role=HouseholdRole.PARENT_ADMIN,
        permissions=frozenset({"family.manage", "family.read"}),
    )


def test_create_and_get_household() -> None:
    service = HouseholdService(InMemoryHouseholdRepository())
    household = Household(
        household_id="home-1",
        tenant_id="tenant-a",
        name="Famille Test",
        members=(make_admin(),),
    )

    assert service.create(household) == household
    assert service.get(tenant_id="tenant-a", household_id="home-1") == household


def test_household_lookup_is_tenant_scoped() -> None:
    service = HouseholdService(InMemoryHouseholdRepository())
    service.create(
        Household(
            household_id="shared-id",
            tenant_id="tenant-a",
            name="Foyer A",
            members=(make_admin(household_id="shared-id"),),
        )
    )

    with pytest.raises(LookupError, match="Household not found"):
        service.get(tenant_id="tenant-b", household_id="shared-id")


def test_add_member_preserves_household_boundary() -> None:
    service = HouseholdService(InMemoryHouseholdRepository())
    service.create(
        Household(
            household_id="home-1",
            tenant_id="tenant-a",
            name="Foyer A",
            members=(make_admin(),),
        )
    )

    child = HouseholdMember(
        member_id="child-1",
        tenant_id="tenant-a",
        household_id="home-1",
        display_name="Enfant",
        role=HouseholdRole.CHILD,
        permissions=frozenset({"education.use", "calendar.read"}),
    )

    updated = service.add_member(
        tenant_id="tenant-a",
        household_id="home-1",
        member=child,
    )

    assert updated.member("child-1") == child
    assert len(updated.members) == 2


def test_reject_member_from_another_tenant() -> None:
    service = HouseholdService(InMemoryHouseholdRepository())
    service.create(
        Household(
            household_id="home-1",
            tenant_id="tenant-a",
            name="Foyer A",
            members=(make_admin(),),
        )
    )

    outsider = HouseholdMember(
        member_id="parent-b",
        tenant_id="tenant-b",
        household_id="home-1",
        display_name="Other Tenant",
        role=HouseholdRole.PARENT_ADMIN,
    )

    with pytest.raises(PermissionError, match="another tenant"):
        service.add_member(
            tenant_id="tenant-a",
            household_id="home-1",
            member=outsider,
        )


def test_non_empty_household_requires_parent_admin() -> None:
    child = HouseholdMember(
        member_id="child-1",
        tenant_id="tenant-a",
        household_id="home-1",
        display_name="Enfant",
        role=HouseholdRole.CHILD,
    )

    with pytest.raises(ValueError, match="parent administrator"):
        Household(
            household_id="home-1",
            tenant_id="tenant-a",
            name="Foyer A",
            members=(child,),
        )
