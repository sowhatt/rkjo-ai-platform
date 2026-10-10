"""Durable notification ledger using PostgreSQL leases and compare-and-set tokens.

Only use with a dedicated database initialized via initialize_schema().
Delivery is at-least-once; channels must honor notification_id for idempotence.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.multimodal.notifications import (
    Notification, NotificationStatus, RetryPolicy,
)


_FIELDS = """notification_id, tenant_id, job_id, channel, recipient_ref,
status, attempts, next_attempt_at, lease_token, last_error"""


def _notification(row: tuple) -> Notification:
    return Notification(
        notification_id=row[0], tenant_id=row[1], job_id=row[2],
        channel=row[3], recipient_ref=row[4], status=NotificationStatus(row[5]),
        attempts=row[6], next_attempt_at=row[7], lease_token=row[8],
        last_error=row[9],
    )


class PostgreSQLNotificationStore:
    def __init__(self, database_url: str, *, max_attempts: int = 4) -> None:
        if not database_url or not database_url.strip():
            raise ValueError("Database URL is required.")
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive.")
        self.database_url = database_url
        self.max_attempts = max_attempts

    def initialize_schema(self) -> None:
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS multimodal_notifications (
                        notification_id TEXT PRIMARY KEY,
                        tenant_id TEXT NOT NULL,
                        job_id TEXT NOT NULL,
                        channel TEXT NOT NULL,
                        recipient_ref TEXT NOT NULL,
                        message_payload JSONB NOT NULL,
                        status TEXT NOT NULL CHECK (status IN
                            ('pending','in_flight','sent','retry','failed')),
                        attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
                        next_attempt_at TIMESTAMPTZ,
                        lease_token TEXT,
                        lease_until TIMESTAMPTZ,
                        provider_ref TEXT,
                        last_error TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        CHECK ((status = 'in_flight') =
                               (lease_token IS NOT NULL AND lease_until IS NOT NULL))
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_multimodal_notifications_due
                    ON multimodal_notifications (next_attempt_at, created_at)
                    WHERE status IN ('pending', 'retry', 'in_flight')
                """)

    @staticmethod
    def _validate_message(message: AgentMessage) -> tuple[str, str, str, str]:
        if (message.message_type != "multimodal.notification.requested" or
                message.target != "rkjo.multimodal.channel_delivery" or
                message.source != "rkjo.multimodal.job_events"):
            raise ValueError("Unsupported notification message.")
        meta = message.metadata
        tenant_id = meta.get("tenant_id")
        job_id = message.payload.get("job_id")
        channel = meta.get("channel")
        recipient_ref = meta.get("recipient_ref")
        if not all(isinstance(v, str) and v.strip()
                   for v in (message.message_id, tenant_id, job_id, channel, recipient_ref)):
            raise ValueError("Notification requires identity and destination.")
        return tenant_id, job_id, channel, recipient_ref

    def register_once(self, message: AgentMessage) -> Notification:
        tenant_id, job_id, channel, recipient_ref = self._validate_message(message)
        body = message.model_dump(mode="json")
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO multimodal_notifications (
                        notification_id, tenant_id, job_id, channel, recipient_ref,
                        message_payload, status
                    ) VALUES (%s,%s,%s,%s,%s,%s,'pending')
                    ON CONFLICT (notification_id) DO NOTHING
                """, (message.message_id, tenant_id, job_id, channel, recipient_ref, Jsonb(body)))
                cur.execute(f"""
                    SELECT {_FIELDS}, message_payload FROM multimodal_notifications
                    WHERE notification_id=%s
                """, (message.message_id,))
                row = cur.fetchone()
                if row is None:
                    raise RuntimeError("Notification insert failed.")
                if row[1:5] != (tenant_id, job_id, channel, recipient_ref) or row[10] != body:
                    raise ValueError("Notification ID conflicts with another payload.")
                return _notification(row)

    def load(self, *, tenant_id: str, notification_id: str) -> Notification | None:
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT {_FIELDS} FROM multimodal_notifications
                    WHERE tenant_id=%s AND notification_id=%s
                """, (tenant_id, notification_id))
                row = cur.fetchone()
                return _notification(row) if row else None

    def claim_due(self, *, now: datetime, lease_seconds: int) -> tuple[Notification, AgentMessage] | None:
        if now.tzinfo is None or now.utcoffset() is None or lease_seconds <= 0:
            raise ValueError("Timezone-aware now and positive lease required.")
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                # An expired lease consumes an attempt even when the worker crashed.
                # Never send an exhausted delivery again.
                cur.execute("""
                    UPDATE multimodal_notifications
                    SET status='failed', lease_token=NULL, lease_until=NULL,
                        next_attempt_at=NULL, last_error='LeaseExpired',
                        updated_at=CURRENT_TIMESTAMP
                    WHERE status='in_flight' AND lease_until<=%s
                      AND attempts >= %s
                      AND NOT (message_payload -> 'payload' ? 'omnichannel_response')
                """, (now, self.max_attempts))
                # Exhausted omnichannel attempts are uncertain, not proof of failure.
                cur.execute("""
                    UPDATE multimodal_notifications SET status='failed',
                        lease_token=NULL, lease_until=NULL,
                        next_attempt_at=NULL,
                        last_error='UncertainProviderAcceptance',
                        updated_at=CURRENT_TIMESTAMP
                    WHERE status='in_flight' AND lease_until<=%s
                      AND attempts >= %s
                      AND message_payload -> 'payload' ? 'omnichannel_response'
                """, (now, self.max_attempts))
                while True:
                    cur.execute(f"""
                    SELECT {_FIELDS}, message_payload, provider_ref
                    FROM multimodal_notifications
                    WHERE attempts < %s AND (
                        (status IN ('pending','retry') AND
                            (next_attempt_at IS NULL OR next_attempt_at<=%s))
                        OR (status='in_flight' AND lease_until<=%s)
                    )
                    ORDER BY created_at, notification_id
                    LIMIT 1 FOR UPDATE SKIP LOCKED
                """, (self.max_attempts, now, now))
                    row = cur.fetchone()
                    if row is None:
                        return None
                    # This check and the subsequent lease change share the row
                    # lock and transaction. Concurrent workers cannot bypass it.
                    payload = row[10].get("payload", {})
                    response = payload.get("omnichannel_response") if isinstance(payload, dict) else None
                    if isinstance(payload, dict) and "omnichannel_response" in payload:
                        if not isinstance(response, dict):
                            cur.execute("""
                                UPDATE multimodal_notifications SET status='failed',
                                    lease_token=NULL,lease_until=NULL,
                                    next_attempt_at=NULL,
                                    last_error='InvalidOmnichannelContract',
                                    updated_at=CURRENT_TIMESTAMP
                                WHERE notification_id=%s AND tenant_id=%s
                            """, (row[0], row[1]))
                            continue
                        cur.execute("""
                            SELECT provider_message_id,channel,channel_account_id
                            FROM omni_delivery_messages
                            WHERE tenant_id=%s AND notification_id=%s
                        """, (row[1], row[0]))
                        proof = cur.fetchone()
                        safe = bool(proof and proof[1] == row[3] and
                            response.get("tenant_id") == row[1] and
                            response.get("notification_id") == row[0] and
                            response.get("channel_account_id") == proof[2] and
                            response.get("recipient_ref") == row[4] and
                            (not row[11] or row[11] == proof[0]))
                        if safe:
                            cur.execute("""
                                UPDATE multimodal_notifications
                                SET status='sent', provider_ref=%s,
                                    lease_token=NULL, lease_until=NULL,
                                    next_attempt_at=NULL, last_error=NULL,
                                    updated_at=CURRENT_TIMESTAMP
                                WHERE notification_id=%s AND tenant_id=%s
                            """, (proof[0], row[0], row[1]))
                        elif row[6] > 0 or row[5] != "pending" or proof is not None:
                            cur.execute("""
                                UPDATE multimodal_notifications
                                SET status='failed', lease_token=NULL,
                                    lease_until=NULL,next_attempt_at=NULL,
                                    last_error='UncertainProviderAcceptance',
                                    updated_at=CURRENT_TIMESTAMP
                                WHERE notification_id=%s AND tenant_id=%s
                            """, (row[0],row[1]))
                            continue
                        if safe:
                            continue
                    claimed = _notification(row)
                    token = uuid4().hex
                    cur.execute("""
                    UPDATE multimodal_notifications
                    SET status='in_flight', attempts=attempts+1,
                        lease_token=%s, lease_until=%s, next_attempt_at=NULL,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE notification_id=%s
                """, (token, now + timedelta(seconds=lease_seconds), claimed.notification_id))
                    return (Notification(
                    notification_id=claimed.notification_id,
                    tenant_id=claimed.tenant_id, job_id=claimed.job_id,
                    channel=claimed.channel, recipient_ref=claimed.recipient_ref,
                    status=NotificationStatus.IN_FLIGHT, attempts=claimed.attempts+1,
                    lease_token=token, last_error=claimed.last_error,
                ), AgentMessage.model_validate(row[10]))

    def mark_sent(self, *, notification_id: str, tenant_id: str,
                  lease_token: str, provider_ref: str) -> None:
        if not lease_token or not provider_ref:
            raise ValueError("Lease token and provider reference required.")
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE multimodal_notifications
                    SET status='sent', lease_token=NULL, lease_until=NULL,
                        next_attempt_at=NULL, provider_ref=%s, last_error=NULL,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE notification_id=%s AND tenant_id=%s
                      AND status='in_flight' AND lease_token=%s
                """, (provider_ref, notification_id, tenant_id, lease_token))
                if cur.rowcount != 1:
                    raise ValueError("Stale notification lease or wrong tenant.")

    def mark_failed(self, *, notification_id: str, tenant_id: str, lease_token: str,
                    now: datetime, error: str, policy: RetryPolicy) -> None:
        if not lease_token or not error:
            raise ValueError("Lease token and error required.")
        if policy.max_attempts != self.max_attempts:
            raise ValueError("Store and worker must use the same maximum attempts.")
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT {_FIELDS} FROM multimodal_notifications
                    WHERE notification_id=%s AND tenant_id=%s
                    FOR UPDATE
                """, (notification_id, tenant_id))
                row = cur.fetchone()
                if row is None or row[8] != lease_token or row[5] != 'in_flight':
                    raise ValueError("Stale notification lease or wrong tenant.")
                updated = policy.on_failure(_notification(row), now=now, error=error)
                cur.execute("""
                    UPDATE multimodal_notifications
                    SET status=%s, lease_token=NULL, lease_until=NULL,
                        next_attempt_at=%s, last_error=%s,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE notification_id=%s AND tenant_id=%s AND lease_token=%s
                """, (updated.status.value, updated.next_attempt_at, updated.last_error,
                      notification_id, tenant_id, lease_token))
                if cur.rowcount != 1:
                    raise ValueError("Concurrent notification update.")

    def mark_terminal(self, *, notification_id: str, tenant_id: str,
                      lease_token: str, error: str) -> None:
        """Terminal rejection, never retry a stale or policy-denied response."""
        if not lease_token or not error:
            raise ValueError("Valid lease token and error required.")
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE multimodal_notifications
                    SET status='failed', lease_token=NULL, lease_until=NULL,
                        next_attempt_at=NULL, last_error=%s,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE notification_id=%s AND tenant_id=%s
                      AND status='in_flight' AND lease_token=%s
                """, (error, notification_id, tenant_id, lease_token))
                if cur.rowcount != 1:
                    raise ValueError("Stale notification lease or wrong tenant.")
