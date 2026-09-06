"""PostgreSQL persistence for RKJO Family households."""

from __future__ import annotations

import json

import psycopg
from psycopg.types.json import Jsonb

from rkjo_family.household.models import (
    Household,
    HouseholdMember,
    HouseholdRole,
)


class PostgresHouseholdRepository:
    """Tenant-safe PostgreSQL repository for household aggregates."""

    def __init__(self, database_url: str) -> None:
        if not database_url.strip():
            raise ValueError("database_url must not be empty.")

        self.database_url = database_url
        self._ensure_schema()

    def _connect(self):
        return psycopg.connect(self.database_url)

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS family_households (
                    tenant_id TEXT NOT NULL,
                    household_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    members JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (tenant_id, household_id)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                family_households_tenant_idx
                ON family_households (tenant_id)
                """
            )

    @staticmethod
    def _member_payload(member: HouseholdMember) -> dict[str, object]:
        return {
            "member_id": member.member_id,
            "tenant_id": member.tenant_id,
            "household_id": member.household_id,
            "display_name": member.display_name,
            "role": member.role.value,
            "permissions": sorted(member.permissions),
        }

    @classmethod
    def _to_members(cls, payload: object) -> tuple[HouseholdMember, ...]:
        if isinstance(payload, str):
            payload = json.loads(payload)

        return tuple(
            HouseholdMember(
                member_id=item["member_id"],
                tenant_id=item["tenant_id"],
                household_id=item["household_id"],
                display_name=item["display_name"],
                role=HouseholdRole(item["role"]),
                permissions=frozenset(item.get("permissions", [])),
            )
            for item in payload
        )

    def save(self, household: Household) -> None:
        members = [self._member_payload(member) for member in household.members]

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO family_households (
                    tenant_id,
                    household_id,
                    name,
                    members
                ) VALUES (%s, %s, %s, %s)
                ON CONFLICT (tenant_id, household_id)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    members = EXCLUDED.members,
                    updated_at = NOW()
                """,
                (
                    household.tenant_id,
                    household.household_id,
                    household.name,
                    Jsonb(members),
                ),
            )

    def get(self, *, tenant_id: str, household_id: str) -> Household | None:
        normalized_tenant = tenant_id.strip()
        normalized_household = household_id.strip()

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT name, members
                FROM family_households
                WHERE tenant_id = %s
                  AND household_id = %s
                """,
                (normalized_tenant, normalized_household),
            ).fetchone()

        if row is None:
            return None

        return Household(
            household_id=normalized_household,
            tenant_id=normalized_tenant,
            name=row[0],
            members=self._to_members(row[1]),
        )

    def list_for_tenant(self, tenant_id: str) -> list[Household]:
        normalized_tenant = tenant_id.strip()

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT household_id, name, members
                FROM family_households
                WHERE tenant_id = %s
                ORDER BY name, household_id
                """,
                (normalized_tenant,),
            ).fetchall()

        return [
            Household(
                household_id=row[0],
                tenant_id=normalized_tenant,
                name=row[1],
                members=self._to_members(row[2]),
            )
            for row in rows
        ]
