"""OMNI-013.3: tenant-bound, idempotent outbound delivery receipt ledger.

Separate from multimodal job notification dispatch: receipts never invoke
agents or update conversation.last_inbound_at. A known outbound provider
message binding must exist before a receipt can update delivery state.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from rkjo_kernel.omnichannel.contracts import DeliveryStatus, DeliveryStatusEvent
from rkjo_kernel.omnichannel.inbound import InboundKind, VerifiedInbound


_PROGRESS = {
    DeliveryStatus.SENT: 1,
    DeliveryStatus.DELIVERED: 2,
    DeliveryStatus.READ: 3,
}
_ALLOWED = frozenset({"sent", "delivered", "read", "failed"})


@dataclass(frozen=True, slots=True)
class DeliverySnapshot:
    tenant_id: str
    notification_id: str
    channel: str
    channel_account_id: str
    provider_message_id: str
    status: DeliveryStatus | None
    occurred_at: datetime | None
    failure_code: str | None


class PostgreSQLDeliveryLedger:
    def __init__(self, database_url: str):
        if not database_url or not database_url.strip():
            raise ValueError("Database URL required.")
        self.database_url = database_url

    def initialize_schema(self):
        with psycopg.connect(self.database_url) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS omni_delivery_messages (
                    tenant_id TEXT NOT NULL,
                    notification_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    channel_account_id TEXT NOT NULL,
                    provider_message_id TEXT NOT NULL,
                    status TEXT CHECK (status IN ('sent','delivered','read','failed')),
                    occurred_at TIMESTAMPTZ,
                    failure_code TEXT,
                    PRIMARY KEY (tenant_id, notification_id),
                    UNIQUE (tenant_id,channel,channel_account_id,provider_message_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS omni_delivery_receipts (
                    tenant_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    channel_account_id TEXT NOT NULL,
                    provider_event_id TEXT NOT NULL,
                    provider_message_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('sent','delivered','read','failed')),
                    occurred_at TIMESTAMPTZ NOT NULL,
                    failure_code TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (tenant_id,channel,channel_account_id,provider_event_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_omni_delivery_receipts_message
                ON omni_delivery_receipts (tenant_id,channel,channel_account_id,provider_message_id)
            """)

    def register_sent(
        self, *, tenant_id: str, notification_id: str, channel: str,
        channel_account_id: str, provider_message_id: str,
    ) -> None:
        """Bind a trusted outbound provider response to its internal notification."""
        values = (tenant_id, notification_id, channel, channel_account_id, provider_message_id)
        if any(not isinstance(v, str) or not v.strip() for v in values):
            raise ValueError("Complete outbound identity required.")
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO omni_delivery_messages
                    (tenant_id,notification_id,channel,channel_account_id,provider_message_id)
                    VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
                """, values)
                cur.execute("""
                    SELECT channel,channel_account_id,provider_message_id
                    FROM omni_delivery_messages
                    WHERE tenant_id=%s AND notification_id=%s FOR UPDATE
                """, (tenant_id, notification_id))
                row = cur.fetchone()
                if row != (channel, channel_account_id, provider_message_id):
                    raise ValueError("Outbound notification binding conflict.")
                # A provider message must not be linked to another notification.
                cur.execute("""
                    SELECT notification_id FROM omni_delivery_messages
                    WHERE tenant_id=%s AND channel=%s AND channel_account_id=%s
                      AND provider_message_id=%s
                """, (tenant_id, channel, channel_account_id, provider_message_id))
                if cur.fetchone() != (notification_id,):
                    raise ValueError("Provider message already bound elsewhere.")

    @staticmethod
    def normalize(event: VerifiedInbound) -> DeliveryStatusEvent:
        if event.kind != InboundKind.DELIVERY_RECEIPT or event.channel != "whatsapp":
            raise ValueError("Only verified WhatsApp delivery receipts are supported.")
        raw = event.payload.get("event")
        if not isinstance(raw, dict):
            raise ValueError("Missing WhatsApp status record.")
        provider_id, raw_status, raw_timestamp = (
            raw.get("id"), raw.get("status"), raw.get("timestamp")
        )
        if (not isinstance(provider_id, str) or not provider_id or
                not isinstance(raw_status, str) or raw_status not in _ALLOWED or
                not isinstance(raw_timestamp, str) or not raw_timestamp.isdecimal()):
            raise ValueError("Invalid WhatsApp delivery status.")
        canonical_id = f"status:{provider_id}:{raw_status}:{raw_timestamp}"
        if event.provider_event_id != canonical_id:
            raise ValueError("Delivery event ID does not match signed payload.")
        try:
            timestamp = datetime.fromtimestamp(int(raw_timestamp), tz=timezone.utc)
        except (OverflowError, ValueError):
            raise ValueError("Invalid receipt timestamp.") from None
        errors = raw.get("errors") or []
        if not isinstance(errors, list):
            raise ValueError("Invalid WhatsApp error list.")
        failure_code = None
        if raw_status == "failed" and errors:
            first = errors[0]
            if not isinstance(first, dict) or not isinstance(first.get("code"), (str, int)):
                raise ValueError("Invalid WhatsApp failure code.")
            failure_code = str(first["code"])
        return DeliveryStatusEvent(
            event_id=event.provider_event_id,
            tenant_id=event.tenant_id,
            channel=event.channel,
            channel_account_id=event.channel_account_id,
            external_message_id=provider_id,
            status=DeliveryStatus(raw_status),
            occurred_at=timestamp,
            received_at=datetime.now(timezone.utc),
            failure_code=failure_code,
        )

    def record(self, event: VerifiedInbound) -> DeliverySnapshot:
        receipt = self.normalize(event)
        key = (receipt.tenant_id,receipt.channel,receipt.channel_account_id,
               receipt.external_message_id)
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT notification_id,status,occurred_at,failure_code
                    FROM omni_delivery_messages
                    WHERE tenant_id=%s AND channel=%s AND channel_account_id=%s
                      AND provider_message_id=%s FOR UPDATE
                """, key)
                row = cur.fetchone()
                if row is None:
                    # Retry from inbound worker; never apply unknown receipts to
                    # another account or tenant.
                    raise LookupError("Unbound outbound provider message.")
                notification_id, prior_status, prior_at, prior_error = row
                cur.execute("""
                    INSERT INTO omni_delivery_receipts
                    (tenant_id,channel,channel_account_id,provider_event_id,
                     provider_message_id,status,occurred_at,failure_code)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT DO NOTHING RETURNING provider_event_id
                """, (*key[:3],receipt.event_id,key[3],receipt.status.value,
                      receipt.occurred_at,receipt.failure_code))
                inserted = cur.fetchone() is not None
                if not inserted:
                    cur.execute("""
                        SELECT provider_message_id,status,occurred_at,failure_code
                        FROM omni_delivery_receipts
                        WHERE tenant_id=%s AND channel=%s AND channel_account_id=%s
                          AND provider_event_id=%s
                    """, (*key[:3],receipt.event_id))
                    existing = cur.fetchone()
                    if existing != (key[3],receipt.status.value,receipt.occurred_at,
                                    receipt.failure_code):
                        raise ValueError("Conflicting receipt replay.")
                # A higher delivery milestone wins. Failed is terminal only until
                # a later positive milestone; never regress from delivered/read.
                should_update = False
                if prior_status is None:
                    should_update = True
                elif receipt.status in _PROGRESS:
                    prior_rank = _PROGRESS.get(DeliveryStatus(prior_status), 0)
                    should_update = _PROGRESS[receipt.status] > prior_rank
                elif prior_status == "failed":
                    should_update = (prior_at is None or receipt.occurred_at > prior_at)
                elif prior_status == "sent":
                    should_update = (prior_at is None or receipt.occurred_at >= prior_at)
                if should_update:
                    cur.execute("""
                        UPDATE omni_delivery_messages
                        SET status=%s,occurred_at=%s,failure_code=%s
                        WHERE tenant_id=%s AND notification_id=%s
                    """, (receipt.status.value,receipt.occurred_at,
                          receipt.failure_code,receipt.tenant_id,notification_id))
                    prior_status, prior_at, prior_error = (
                        receipt.status.value,receipt.occurred_at,receipt.failure_code
                    )
                return DeliverySnapshot(
                    tenant_id=receipt.tenant_id, notification_id=notification_id,
                    channel=receipt.channel, channel_account_id=receipt.channel_account_id,
                    provider_message_id=receipt.external_message_id,
                    status=DeliveryStatus(prior_status) if prior_status else None,
                    occurred_at=prior_at, failure_code=prior_error,
                )

    def load(self, *, tenant_id: str, notification_id: str) -> DeliverySnapshot | None:
        with psycopg.connect(self.database_url) as conn:
            row = conn.execute("""
                SELECT channel,channel_account_id,provider_message_id,
                       status,occurred_at,failure_code
                FROM omni_delivery_messages
                WHERE tenant_id=%s AND notification_id=%s
            """, (tenant_id,notification_id)).fetchone()
        if row is None:
            return None
        return DeliverySnapshot(
            tenant_id,notification_id,row[0],row[1],row[2],
            DeliveryStatus(row[3]) if row[3] else None,row[4],row[5],
        )


class DeliveryReceiptHandler:
    """Safe receipt handler plug-in for InboundProcessingWorker."""
    def __init__(self, ledger: PostgreSQLDeliveryLedger):
        self.ledger = ledger

    def handle(self, event: VerifiedInbound) -> None:
        self.ledger.record(event)
