"""Household application service."""

from __future__ import annotations

from dataclasses import replace

from rkjo_family.household.models import Household, HouseholdMember
from rkjo_family.household.repository import HouseholdRepository


class HouseholdService:
    def __init__(self, repository: HouseholdRepository) -> None:
        self.repository = repository

    def create(self, household: Household) -> Household:
        existing = self.repository.get(
            tenant_id=household.tenant_id,
            household_id=household.household_id,
        )
        if existing is not None:
            raise ValueError("Household already exists.")

        self.repository.save(household)
        return household

    def get(self, *, tenant_id: str, household_id: str) -> Household:
        normalized_tenant_id = tenant_id.strip()
        normalized_household_id = household_id.strip()

        if not normalized_tenant_id:
            raise ValueError("tenant_id must not be empty.")
        if not normalized_household_id:
            raise ValueError("household_id must not be empty.")

        household = self.repository.get(
            tenant_id=normalized_tenant_id,
            household_id=normalized_household_id,
        )
        if household is None:
            raise LookupError("Household not found.")
        return household

    def list_households(self, *, tenant_id: str) -> list[Household]:
        normalized_tenant_id = tenant_id.strip()
        if not normalized_tenant_id:
            raise ValueError("tenant_id must not be empty.")
        return self.repository.list_for_tenant(normalized_tenant_id)

    def add_member(
        self,
        *,
        tenant_id: str,
        household_id: str,
        member: HouseholdMember,
    ) -> Household:
        household = self.get(tenant_id=tenant_id, household_id=household_id)

        if member.tenant_id != household.tenant_id:
            raise PermissionError("Member belongs to another tenant.")
        if member.household_id != household.household_id:
            raise ValueError("Member belongs to another household.")
        if household.member(member.member_id) is not None:
            raise ValueError("Household member already exists.")

        updated = replace(household, members=(*household.members, member))
        self.repository.save(updated)
        return updated

    def require_member(
        self,
        *,
        tenant_id: str,
        household_id: str,
        member_id: str,
    ) -> HouseholdMember:
        household = self.get(tenant_id=tenant_id, household_id=household_id)
        member = household.member(member_id)
        if member is None:
            raise LookupError("Household member not found.")
        return member
