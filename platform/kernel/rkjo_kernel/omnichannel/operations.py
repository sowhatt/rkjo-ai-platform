"""OMNI-015.4: tenant-scoped operational cockpit read model.

Read-only, no PII or raw webhook payload returned. Dashboard access must be
protected by the hosting API's tenant authentication and authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import psycopg


@dataclass(frozen=True, slots=True)
class QueueHealth:
    pending: int
    failed: int
    expired_leases: int


@dataclass(frozen=True, slots=True)
class OperationalSnapshot:
    tenant_id: str
    inbound: QueueHealth
    routes: QueueHealth
    outbound: QueueHealth
    uncertain_outbound: int
    provider_confirmed_uncommitted: int
    sent_without_binding: int
    delivery_receipts: int


class PostgreSQLOmnichannelOperations:
    def __init__(self, database_url: str):
        if not database_url or not database_url.strip():
            raise ValueError("Database URL required.")
        self.database_url = database_url

    def snapshot(self, *, tenant_id: str, now: datetime) -> OperationalSnapshot:
        if not tenant_id or not tenant_id.strip():
            raise ValueError("Tenant required.")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Timezone-aware clock required.")
        with psycopg.connect(self.database_url) as conn:
            def health(table: str, waiting: str, expired: str) -> QueueHealth:
                # Callers cannot inject SQL identifiers; only fixed internal strings.
                row = conn.execute(f"""
                    SELECT count(*) FILTER (WHERE {waiting}),
                           count(*) FILTER (WHERE status='failed'),
                           count(*) FILTER (WHERE {expired})
                    FROM {table} WHERE tenant_id=%s
                """, (now, tenant_id)).fetchone()
                return QueueHealth(*(int(v or 0) for v in row))

            inbound = health("omni_inbound_events",
                             "status='pending'",
                             "status='pending' AND lease_token IS NOT NULL AND lease_until<=%s" )
            routes = health("omni_route_outbox",
                            "status='pending'",
                            "status='pending' AND lease_token IS NOT NULL AND lease_until<=%s")
            outbound = health("multimodal_notifications",
                              "status IN ('pending','retry','in_flight')",
                              "status='in_flight' AND lease_until<=%s")
            row = conn.execute("""
                SELECT
                  count(*) FILTER (
                    WHERE n.status IN ('retry','in_flight')
                      AND (n.status='retry' OR n.lease_until<=%s)
                      AND d.notification_id IS NULL
                  ),
                  count(*) FILTER (
                    WHERE n.status IN ('retry','in_flight','failed')
                      AND d.notification_id IS NOT NULL
                  ),
                  count(*) FILTER (
                    WHERE n.status='sent' AND d.notification_id IS NULL
                  )
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
            """, (now, tenant_id)).fetchone()
            receipts = conn.execute("""
                SELECT count(*) FROM omni_delivery_receipts WHERE tenant_id=%s
            """, (tenant_id,)).fetchone()[0]
        return OperationalSnapshot(
            tenant_id=tenant_id, inbound=inbound, routes=routes,
            outbound=outbound, uncertain_outbound=int(row[0] or 0),
            provider_confirmed_uncommitted=int(row[1] or 0),
            sent_without_binding=int(row[2] or 0),
            delivery_receipts=int(receipts),
        )
