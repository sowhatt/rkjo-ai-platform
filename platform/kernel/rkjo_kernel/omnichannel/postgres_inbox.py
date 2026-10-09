"""PostgreSQL tenant-scoped webhook inbox.

Registration is atomic and idempotent. Rows are left pending for separate
receipt / user-message processors. No processing ACK is implied by insertion.
"""
from __future__ import annotations

import json

import psycopg
from psycopg.types.json import Jsonb

from rkjo_kernel.omnichannel.inbound import VerifiedInbound


class PostgreSQLInboundInbox:
    def __init__(self, database_url: str):
        if not database_url or not database_url.strip():
            raise ValueError("Database URL required.")
        self.database_url = database_url

    def initialize_schema(self) -> None:
        with psycopg.connect(self.database_url) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS omni_inbound_events (
                    tenant_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    channel_account_id TEXT NOT NULL,
                    provider_event_id TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK (
                        kind IN ('user_message', 'delivery_receipt', 'ignored')
                    ),
                    payload JSONB NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'processed', 'failed')),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMPTZ,
                    PRIMARY KEY (tenant_id, channel, channel_account_id, provider_event_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_omni_inbound_pending
                ON omni_inbound_events (created_at)
                WHERE status = 'pending' AND kind <> 'ignored'
            """)

    def accept_once(self, event: VerifiedInbound) -> bool:
        # Do not log payload: it may contain personal information.
        document = json.loads(json.dumps(dict(event.payload)))
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO omni_inbound_events (
                        tenant_id, channel, channel_account_id,
                        provider_event_id, kind, payload, status
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT DO NOTHING
                    RETURNING provider_event_id
                """, (
                    event.tenant_id, event.channel, event.channel_account_id,
                    event.provider_event_id, event.kind.value, Jsonb(document),
                    "processed" if event.kind.value == "ignored" else "pending",
                ))
                inserted = cur.fetchone() is not None
                if inserted:
                    return True
                cur.execute("""
                    SELECT kind, payload FROM omni_inbound_events
                    WHERE tenant_id=%s AND channel=%s
                      AND channel_account_id=%s AND provider_event_id=%s
                """, (
                    event.tenant_id, event.channel,
                    event.channel_account_id, event.provider_event_id,
                ))
                existing = cur.fetchone()
                if existing is None or existing != (event.kind.value, document):
                    raise ValueError("Webhook event identity collides with different content.")
                return False
