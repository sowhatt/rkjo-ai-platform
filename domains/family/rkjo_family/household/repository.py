"""Household repositories."""

from __future__ import annotations

from typing import Protocol

from rkjo_family.household.models import Household


class HouseholdRepository(Protocol):
    def save(self, household: Household) -> None:
        ...

    def get(self, *, tenant_id: str, household_id: str) -> Household | None:
        ...

    def list_for_tenant(self, tenant_id: str) -> list[Household]:
        ...


class InMemoryHouseholdRepository:
    """Reference repository used by unit tests and early domain wiring."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str], Household] = {}

    def save(self, household: Household) -> None:
        self._items[(household.tenant_id, household.household_id)] = household

    def get(self, *, tenant_id: str, household_id: str) -> Household | None:
        return self._items.get((tenant_id.strip(), household_id.strip()))

    def list_for_tenant(self, tenant_id: str) -> list[Household]:
        normalized_tenant_id = tenant_id.strip()
        return [
            household
            for (stored_tenant_id, _), household in self._items.items()
            if stored_tenant_id == normalized_tenant_id
        ]
