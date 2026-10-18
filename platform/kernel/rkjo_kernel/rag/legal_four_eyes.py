"""Four-eyes legal review decision engine, without any RAG publication.

All rules are evaluated on a serialized PostgreSQL transaction. Reviewers
are granted independently per tenant and dossier by a trusted administrator.
The author of the submitted packet cannot approve it.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import psycopg
from psycopg import sql


@dataclass(frozen=True, slots=True)
class FourEyesResult:
    state: str
    reviewer_count: int
    publishable: bool = False


class LegalFourEyesWorkflow:
    def __init__(self, *, database_url: str, table_prefix: str = "lexia_legal"):
        if not database_url.strip():
            raise ValueError("database_url required")
        if not table_prefix or not table_prefix.replace("_", "").isalnum():
            raise ValueError("invalid table prefix")
        self.url = database_url
        self.items = table_prefix + "_review_items"
        self.events = table_prefix + "_review_events"
        self.grants = table_prefix + "_review_grants"
        self.decisions = table_prefix + "_four_eyes_decisions"

    def initialize_schema(self):
        """Controlled migration. Requires inbox schema to exist."""
        with psycopg.connect(self.url, autocommit=True) as conn:
            conn.execute(sql.SQL("""
                CREATE TABLE IF NOT EXISTS {} (
                    tenant_id TEXT NOT NULL,
                    dossier_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    granted_by TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, dossier_id, actor_id)
                )
            """).format(sql.Identifier(self.grants)))
            conn.execute(sql.SQL("""
                CREATE TABLE IF NOT EXISTS {} (
                    packet_id UUID NOT NULL,
                    tenant_id TEXT NOT NULL,
                    dossier_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    note TEXT NOT NULL CHECK (length(trim(note)) > 0),
                    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (packet_id, tenant_id, actor_id),
                    FOREIGN KEY (packet_id, tenant_id)
                        REFERENCES {} (packet_id, tenant_id)
                )
            """).format(sql.Identifier(self.decisions), sql.Identifier(self.items)))

    def grant_reviewer(self, *, tenant_id: str, dossier_id: str,
                       actor_id: str, granted_by: str):
        """Administrative provisioning only. NEVER expose to a reviewer endpoint."""
        self._nonempty(tenant_id, dossier_id, actor_id, granted_by)
        if actor_id == granted_by:
            raise PermissionError("Self-grant prohibited")
        with psycopg.connect(self.url) as conn:
            conn.execute(sql.SQL("""
                INSERT INTO {} (tenant_id, dossier_id, actor_id, granted_by)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (tenant_id, dossier_id, actor_id) DO NOTHING
            """).format(sql.Identifier(self.grants)),
                         (tenant_id, dossier_id, actor_id, granted_by))

    def verify(
        self, *, packet_id: UUID, tenant_id: str, dossier_id: str,
        actor_id: str, note: str,
    ) -> FourEyesResult | None:
        """Apply one human decision atomically; NEVER publish or change trust."""
        self._nonempty(tenant_id, dossier_id, actor_id, note)
        if len(note) > 4000:
            raise ValueError("Note too long")
        with psycopg.connect(self.url) as conn:
            row = conn.execute(sql.SQL("""
                SELECT state, metadata FROM {}
                WHERE packet_id = %s AND tenant_id = %s FOR UPDATE
            """).format(sql.Identifier(self.items)), (packet_id, tenant_id)).fetchone()
            if row is None:
                return None
            state, metadata = row
            if state != "awaiting_human_review":
                raise PermissionError("Packet cannot be reviewed")
            if metadata.get("dossier_id") != dossier_id:
                raise PermissionError("Dossier mismatch")
            permitted = conn.execute(sql.SQL("""
                SELECT 1 FROM {} WHERE tenant_id=%s AND dossier_id=%s AND actor_id=%s
            """).format(sql.Identifier(self.grants)),
                (tenant_id, dossier_id, actor_id)).fetchone()
            if not permitted:
                raise PermissionError("Not an authorized reviewer")

            submitter = conn.execute(sql.SQL("""
                SELECT actor_id FROM {} WHERE packet_id=%s
                AND tenant_id=%s AND action='submitted'
                ORDER BY event_id LIMIT 1
            """).format(sql.Identifier(self.events)), (packet_id, tenant_id)).fetchone()
            if not submitter or actor_id == submitter[0]:
                raise PermissionError("Submitter cannot approve own packet")

            rejected = conn.execute(sql.SQL("""
                SELECT 1 FROM {} WHERE packet_id=%s AND tenant_id=%s
                AND action='rejected' LIMIT 1
            """).format(sql.Identifier(self.events)), (packet_id, tenant_id)).fetchone()
            if rejected:
                raise PermissionError("Rejected packet cannot be reviewed")

            existing = conn.execute(sql.SQL("""
                SELECT actor_id FROM {} WHERE packet_id=%s AND tenant_id=%s
                FOR UPDATE
            """).format(sql.Identifier(self.decisions)),
                (packet_id, tenant_id)).fetchall()
            if actor_id in {r[0] for r in existing}:
                raise PermissionError("Same reviewer cannot verify twice")
            if len(existing) >= 2:
                raise PermissionError("Review is already complete")

            conn.execute(sql.SQL("""
                INSERT INTO {} (packet_id, tenant_id, dossier_id, actor_id, note)
                VALUES (%s, %s, %s, %s, %s)
            """).format(sql.Identifier(self.decisions)),
                (packet_id, tenant_id, dossier_id, actor_id, note.strip()))
            count = len(existing) + 1
            return FourEyesResult(
                state="two_reviews_recorded" if count == 2 else "awaiting_second_review",
                reviewer_count=count,
            )

    def drop_schema(self):
        """Disposable test databases ONLY; never expose over HTTP."""
        with psycopg.connect(self.url, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(self.decisions)))
            conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(self.grants)))

    @staticmethod
    def _nonempty(*values):
        if any(not isinstance(v, str) or not v.strip() for v in values):
            raise ValueError("Nonempty identity, dossier and note required")
