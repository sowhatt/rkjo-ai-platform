"""Household domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


def _required(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    return normalized


class HouseholdRole(StrEnum):
    PARENT_ADMIN = "parent_admin"
    PARENT = "parent"
    CHILD = "child"


@dataclass(frozen=True, slots=True)
class HouseholdMember:
    member_id: str
    tenant_id: str
    household_id: str
    display_name: str
    role: HouseholdRole
    permissions: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        for field_name in (
            "member_id",
            "tenant_id",
            "household_id",
            "display_name",
        ):
            object.__setattr__(
                self,
                field_name,
                _required(getattr(self, field_name), field_name=field_name),
            )

        normalized_permissions = frozenset(
            _required(permission, field_name="permission")
            for permission in self.permissions
        )
        object.__setattr__(self, "permissions", normalized_permissions)

    @property
    def is_admin(self) -> bool:
        return self.role is HouseholdRole.PARENT_ADMIN


@dataclass(frozen=True, slots=True)
class Household:
    household_id: str
    tenant_id: str
    name: str
    members: tuple[HouseholdMember, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for field_name in ("household_id", "tenant_id", "name"):
            object.__setattr__(
                self,
                field_name,
                _required(getattr(self, field_name), field_name=field_name),
            )

        seen_member_ids: set[str] = set()
        for member in self.members:
            if member.tenant_id != self.tenant_id:
                raise ValueError("Member tenant_id must match household tenant_id.")
            if member.household_id != self.household_id:
                raise ValueError(
                    "Member household_id must match household household_id."
                )
            if member.member_id in seen_member_ids:
                raise ValueError("Household member_id values must be unique.")
            seen_member_ids.add(member.member_id)

        if self.members and not any(member.is_admin for member in self.members):
            raise ValueError("A non-empty household must have a parent administrator.")

    def member(self, member_id: str) -> HouseholdMember | None:
        normalized = _required(member_id, field_name="member_id")
        return next(
            (member for member in self.members if member.member_id == normalized),
            None,
        )
