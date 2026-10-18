"""Tenant-scoped PostgreSQL inbox for legal sources awaiting professional review.

Separate from RAG chunks. No approval/publishing API is provided. Each review
event is append-only and records the authenticated actor supplied by the caller.
The backend must obtain tenant/actor from verified credentials, never form data.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from rkjo_kernel.rag.legal_intake import LegalIntakePacket


@dataclass(frozen=True, slots=True)
class ReviewEvent:
    packet_id: UUID
    tenant_id: str
    actor_id: str
    action: str
    note: str
    occurred_at: datetime


class PostgresLegalReviewInbox:
    """Durable quarantine metadata and non-promoting review audit."""

    def __init__(self, *, database_url: str, table_prefix: str = "lexia_legal"):
        if not database_url.strip():
            raise ValueError("database_url required")
        if not table_prefix or not table_prefix.replace("_", "").isalnum():
            raise ValueError("invalid table_prefix")
        self.database_url = database_url
        self.items = table_prefix + "_review_items"
        self.events = table_prefix + "_review_events"

    def initialize_schema(self):
        with psycopg.connect(self.database_url, autocommit=True) as conn:
            conn.execute(sql.SQL("""
                CREATE TABLE IF NOT EXISTS {} (
                    packet_id UUID PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (
                        state IN ('quarantined', 'awaiting_human_review')
                    ),
                    document_sha256 TEXT NOT NULL,
                    metadata JSONB NOT NULL,
                    reasons JSONB NOT NULL,
                    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (packet_id, tenant_id)
                )
            """).format(sql.Identifier(self.items)))
            conn.execute(sql.SQL("""
                CREATE TABLE IF NOT EXISTS {} (
                    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    packet_id UUID NOT NULL,
                    tenant_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    action TEXT NOT NULL CHECK (
                        action IN ('submitted', 'review_requested', 'review_note', 'rejected')
                    ),
                    note TEXT NOT NULL,
                    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    FOREIGN KEY (packet_id, tenant_id)
                        REFERENCES {} (packet_id, tenant_id)
                )
            """).format(sql.Identifier(self.events), sql.Identifier(self.items)))

    def submit(self, *, packet: LegalIntakePacket, tenant_id: str, actor_id: str) -> UUID:
        """Store metadata only, never source bytes; write initial audit atomically."""
        self._require_identity(tenant_id, actor_id)
        if packet.metadata.get("tenant_id") != tenant_id:
            raise PermissionError("Cannot submit to another tenant")
        if packet.state not in ("quarantined", "awaiting_human_review"):
            raise ValueError("Invalid review state")
        if packet.can_index_as_verified:
            raise ValueError("Verified material cannot enter unverified inbox")

        packet_id = uuid4()
        with psycopg.connect(self.database_url) as conn:
            conn.execute(sql.SQL("""
                INSERT INTO {} (packet_id, tenant_id, state, document_sha256, metadata, reasons)
                VALUES (%s, %s, %s, %s, %s, %s)
            """).format(sql.Identifier(self.items)), (
                packet_id, tenant_id, packet.state, packet.document_sha256,
                Jsonb(packet.metadata), Jsonb(list(packet.reasons)),
            ))
            self._insert_event(conn, packet_id, tenant_id, actor_id, "submitted", "")
        return packet_id

    def append_review_event(
        self, *, packet_id: UUID, tenant_id: str, actor_id: str,
        action: str, note: str,
    ) -> bool:
        """Record review progress, never promote a candidate to indexed/legal truth."""
        self._require_identity(tenant_id, actor_id)
        if action not in {"review_requested", "review_note", "rejected"}:
            raise ValueError("Action not allowed")
        if not isinstance(note, str) or not note.strip():
            raise ValueError("A review note is required")
        with psycopg.connect(self.database_url) as conn:
            row = conn.execute(sql.SQL("""
                SELECT 1 FROM {} WHERE packet_id = %s AND tenant_id = %s
                FOR UPDATE
            """).format(sql.Identifier(self.items)), (packet_id, tenant_id)).fetchone()
            if row is None:
                return False
            self._insert_event(conn, packet_id, tenant_id, actor_id, action, note.strip())
        return True

    def list_review_events(self, *, packet_id: UUID, tenant_id: str) -> list[ReviewEvent]:
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("Authenticated tenant required")
        with psycopg.connect(self.database_url) as conn:
            rows = conn.execute(sql.SQL("""
                SELECT packet_id, tenant_id, actor_id, action, note, occurred_at
                FROM {} WHERE packet_id = %s AND tenant_id = %s
                ORDER BY event_id ASC
            """).format(sql.Identifier(self.events)), (packet_id, tenant_id)).fetchall()
        return [ReviewEvent(*row) for row in rows]

    def drop_schema(self):
        """ONLY for disposable test databases with uniquely named tables."""
        with psycopg.connect(self.database_url, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(self.events)))
            conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(self.items)))

    @staticmethod
    def _require_identity(tenant_id: str, actor_id: str):
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("Authenticated tenant required")
        if not isinstance(actor_id, str) or not actor_id.strip():
            raise ValueError("Authenticated actor required")

    def _insert_event(self, conn, packet_id, tenant_id, actor_id, action, note):
        conn.execute(sql.SQL("""
            INSERT INTO {} (packet_id, tenant_id, actor_id, action, note)
            VALUES (%s, %s, %s, %s, %s)
        """).format(sql.Identifier(self.events)), (
            packet_id, tenant_id, actor_id, action, note,
        ))
