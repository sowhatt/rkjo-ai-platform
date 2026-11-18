"""OMNI-015.3: safe reconciliation and operational read model.

Only explicit omnichannel notifications are considered. A persisted provider
binding is proof of provider acceptance, NOT proof of delivery. This code never
retransmits, guesses a provider reference, or reconciles an active lease.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import psycopg


@dataclass(frozen=True, slots=True)
class DeliveryReconciliationReport:
    tenant_id: str
    repaired: int
    provider_confirmed_uncommitted: int
    expired_unconfirmed: int
    sent_without_binding: int
    failed: int


class OmnichannelDeliveryReconciler:
    def __init__(self, database_url: str):
        if not database_url or not database_url.strip():
            raise ValueError("Database URL required.")
        self.database_url = database_url

    @staticmethod
    def _validate(tenant_id: str, now: datetime) -> None:
        if not tenant_id or not tenant_id.strip():
            raise ValueError("Explicit tenant required.")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Timezone-aware clock required.")

    def reconcile(self, *, tenant_id: str, now: datetime) -> DeliveryReconciliationReport:
        """Repair only stale outbound rows backed by matching provider binding.

        Lease-expired in_flight and retry rows are safe to reconcile. The
        UPDATE locks notifications; a concurrently claimed active lease is not
        overwritten. Without provider proof, emit a warning, never resend.
        """
        self._validate(tenant_id, now)
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE multimodal_notifications n
                    SET status='sent', provider_ref=d.provider_message_id,
                        lease_token=NULL, lease_until=NULL,
                        next_attempt_at=NULL, last_error=NULL,
                        updated_at=CURRENT_TIMESTAMP
                    FROM omni_delivery_messages d
                    WHERE n.tenant_id=%s AND d.tenant_id=n.tenant_id
                      AND d.notification_id=n.notification_id
                      AND d.channel=n.channel
                      AND n.message_payload -> 'payload' -> 'omnichannel_response'
                          ->> 'channel_account_id' = d.channel_account_id
                      AND n.message_payload -> 'payload' -> 'omnichannel_response'
                          ->> 'notification_id' = n.notification_id
                      AND n.message_payload -> 'payload' -> 'omnichannel_response'
                          ->> 'tenant_id' = n.tenant_id
                      AND n.message_payload -> 'payload' -> 'omnichannel_response'
                          ->> 'recipient_ref' = n.recipient_ref
                      AND n.status IN ('in_flight','retry','failed')
                      AND (n.status <> 'in_flight' OR n.lease_until <= %s)
                      AND (n.provider_ref IS NULL OR n.provider_ref=d.provider_message_id)
                """, (tenant_id, now))
                repaired = cur.rowcount
                cur.execute("""
                    SELECT n.status, n.lease_until, d.provider_message_id,
                           n.provider_ref
                    FROM multimodal_notifications n
                    LEFT JOIN omni_delivery_messages d
                      ON d.tenant_id=n.tenant_id
                     AND d.notification_id=n.notification_id
                     AND d.channel=n.channel
                     AND d.channel_account_id=(
                         n.message_payload -> 'payload' -> 'omnichannel_response'
                         ->> 'channel_account_id'
                     )
                    WHERE n.tenant_id=%s
                      AND n.message_payload -> 'payload' ? 'omnichannel_response'
                """, (tenant_id,))
                rows = cur.fetchall()
        confirmed_uncommitted = 0
        expired_unconfirmed = 0
        sent_unbound = 0
        failed = 0
        for status, lease_until, provider_binding, provider_ref in rows:
            if status == "sent" and provider_binding is None:
                sent_unbound += 1
            elif status in ("in_flight", "retry", "failed") and provider_binding:
                confirmed_uncommitted += 1
            elif status == "in_flight" and lease_until is not None and lease_until <= now and not provider_binding:
                expired_unconfirmed += 1
            elif status == "failed":
                failed += 1
        return DeliveryReconciliationReport(
            tenant_id=tenant_id,
            repaired=repaired,
            provider_confirmed_uncommitted=confirmed_uncommitted,
            expired_unconfirmed=expired_unconfirmed,
            sent_without_binding=sent_unbound,
            failed=failed,
        )

    def quarantine_uncertain(self, *, tenant_id: str, now: datetime) -> int:
        """Freeze expired/retry omnichannel sends with no provider proof.

        Must execute before dispatch workers claim more rows. This operation
        locks matching notifications and never marks a send as unsuccessful
        with certainty; failed here means 'manual reconciliation required'.
        """
        self._validate(tenant_id, now)
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE multimodal_notifications n
                    SET status='failed', lease_token=NULL, lease_until=NULL,
                        next_attempt_at=NULL,
                        last_error='UncertainProviderAcceptance',
                        updated_at=CURRENT_TIMESTAMP
                    WHERE n.tenant_id=%s
                      AND n.message_payload -> 'payload' ? 'omnichannel_response'
                      AND n.attempts > 0
                      AND (n.status='retry'
                           OR (n.status='in_flight' AND n.lease_until<=%s))
                      AND NOT EXISTS (
                        SELECT 1 FROM omni_delivery_messages d
                        WHERE d.tenant_id=n.tenant_id
                          AND d.notification_id=n.notification_id
                          AND d.channel=n.channel
                      )
                """, (tenant_id, now))
                return cur.rowcount
