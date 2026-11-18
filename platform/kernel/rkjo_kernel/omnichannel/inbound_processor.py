"""OMNI-013.1: leased PostgreSQL inbox processing.

At-least-once processing. Downstream handlers MUST be idempotent using the
(tenant, channel, account, event_id) key. The inbox cannot atomically commit
an external provider side-effect; never claim exactly-once delivery.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import uuid4

import psycopg

from rkjo_kernel.omnichannel.inbound import InboundKind, VerifiedInbound


@dataclass(frozen=True, slots=True)
class ClaimedInbound:
    event: VerifiedInbound
    lease_token: str
    attempt: int


class InboundEventHandler(Protocol):
    def handle(self, event: VerifiedInbound) -> None: ...


class PostgreSQLInboundProcessorStore:
    def __init__(self, database_url: str, *, max_attempts: int = 4):
        if not database_url or not database_url.strip() or max_attempts < 1:
            raise ValueError("Database URL and positive max_attempts required.")
        self.database_url = database_url
        self.max_attempts = max_attempts

    def initialize_schema(self):
        # Safe for an existing OMNI-010/012 inbox table. This migration is
        # additive; older producers can continue registering events.
        with psycopg.connect(self.database_url) as conn:
            conn.execute("""
                ALTER TABLE omni_inbound_events
                ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0
            """)
            conn.execute("""
                ALTER TABLE omni_inbound_events
                ADD COLUMN IF NOT EXISTS lease_token TEXT
            """)
            conn.execute("""
                ALTER TABLE omni_inbound_events
                ADD COLUMN IF NOT EXISTS lease_until TIMESTAMPTZ
            """)
            conn.execute("""
                ALTER TABLE omni_inbound_events
                ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ
            """)
            conn.execute("""
                ALTER TABLE omni_inbound_events
                ADD COLUMN IF NOT EXISTS last_error TEXT
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_omni_inbound_leases
                ON omni_inbound_events (next_attempt_at, created_at)
                WHERE status='pending'
            """)

    @staticmethod
    def _key(event: VerifiedInbound):
        return (event.tenant_id, event.channel, event.channel_account_id, event.provider_event_id)

    @staticmethod
    def _check_now(now: datetime):
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Timezone-aware clock required.")

    def claim_due(self, *, now: datetime, lease_seconds: int = 30) -> ClaimedInbound | None:
        self._check_now(now)
        if lease_seconds <= 0:
            raise ValueError("Positive lease required.")
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE omni_inbound_events SET status='failed',
                        lease_token=NULL, lease_until=NULL,
                        last_error='MaxAttemptsExceeded'
                    WHERE status='pending' AND attempts >= %s
                      AND (lease_until IS NULL OR lease_until <= %s)
                """, (self.max_attempts, now))
                cur.execute("""
                    SELECT tenant_id, channel, channel_account_id,
                           provider_event_id, kind, payload, attempts
                    FROM omni_inbound_events
                    WHERE status='pending' AND kind <> 'ignored'
                      AND attempts < %s
                      AND (lease_until IS NULL OR lease_until <= %s)
                      AND (next_attempt_at IS NULL OR next_attempt_at <= %s)
                    ORDER BY created_at, tenant_id, channel, provider_event_id
                    LIMIT 1 FOR UPDATE SKIP LOCKED
                """, (self.max_attempts, now, now))
                row = cur.fetchone()
                if row is None:
                    return None
                event = VerifiedInbound(
                    tenant_id=row[0], channel=row[1], channel_account_id=row[2],
                    provider_event_id=row[3], kind=InboundKind(row[4]), payload=row[5],
                )
                token = uuid4().hex
                cur.execute("""
                    UPDATE omni_inbound_events SET attempts=attempts+1,
                        lease_token=%s, lease_until=%s, next_attempt_at=NULL
                    WHERE tenant_id=%s AND channel=%s AND channel_account_id=%s
                      AND provider_event_id=%s
                """, (token, now + timedelta(seconds=lease_seconds), *self._key(event)))
                return ClaimedInbound(event=event, lease_token=token, attempt=row[6] + 1)

    def mark_processed(self, claim: ClaimedInbound) -> None:
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE omni_inbound_events
                    SET status='processed', processed_at=CURRENT_TIMESTAMP,
                        lease_token=NULL, lease_until=NULL,
                        next_attempt_at=NULL, last_error=NULL
                    WHERE tenant_id=%s AND channel=%s AND channel_account_id=%s
                      AND provider_event_id=%s AND status='pending'
                      AND lease_token=%s
                """, (*self._key(claim.event), claim.lease_token))
                if cur.rowcount != 1:
                    raise ValueError("Stale lease or tenant mismatch.")

    def mark_failed(self, claim: ClaimedInbound, *, now: datetime,
                    error: str, retry_delay_seconds: int = 5) -> None:
        self._check_now(now)
        if retry_delay_seconds < 0 or not error:
            raise ValueError("Invalid retry parameters.")
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE omni_inbound_events
                    SET status=CASE WHEN attempts >= %s THEN 'failed'
                                    ELSE 'pending' END,
                        lease_token=NULL, lease_until=NULL,
                        next_attempt_at=CASE WHEN attempts >= %s THEN NULL ELSE %s END,
                        last_error=%s
                    WHERE tenant_id=%s AND channel=%s AND channel_account_id=%s
                      AND provider_event_id=%s AND status='pending'
                      AND lease_token=%s
                """, (
                    self.max_attempts, self.max_attempts,
                    now + timedelta(seconds=retry_delay_seconds), error[:200],
                    *self._key(claim.event), claim.lease_token,
                ))
                if cur.rowcount != 1:
                    raise ValueError("Stale lease or tenant mismatch.")


class InboundProcessingWorker:
    def __init__(self, *, store: PostgreSQLInboundProcessorStore,
                 user_messages: InboundEventHandler,
                 delivery_receipts: InboundEventHandler,
                 lease_seconds: int = 30):
        self.store = store
        self.user_messages = user_messages
        self.delivery_receipts = delivery_receipts
        self.lease_seconds = lease_seconds

    def run_once(self, *, now: datetime) -> bool:
        claim = self.store.claim_due(now=now, lease_seconds=self.lease_seconds)
        if claim is None:
            return False
        try:
            if claim.event.kind == InboundKind.USER_MESSAGE:
                self.user_messages.handle(claim.event)
            elif claim.event.kind == InboundKind.DELIVERY_RECEIPT:
                self.delivery_receipts.handle(claim.event)
            else:
                raise ValueError("Unsupported inbox event kind.")
        except Exception as exc:
            # Avoid logging message contents or recipient identifiers.
            self.store.mark_failed(claim, now=now, error=type(exc).__name__)
            return True
        self.store.mark_processed(claim)
        return True
