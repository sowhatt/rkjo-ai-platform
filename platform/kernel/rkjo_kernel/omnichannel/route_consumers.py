"""OMNI-014.2 integration adapters for RKJO Agent Runtime and operator inbox.

The agent adapter emits the EXISTING AgentMessage on the EXISTING EventBus.
It does not execute an agent or bypass upstream policy. Deployment must bind
agent_name/queue to an authorized, policy-enabled agent runtime.

At-least-once transport: downstream agent consumers must deduplicate message_id.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import psycopg
from psycopg.types.json import Jsonb

from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.omnichannel.conversation_router import RoutedInbound
from rkjo_kernel.omnichannel.inbound import InboundKind, VerifiedInbound


def route_id(route: RoutedInbound) -> str:
    """Tenant-scoped, stable and opaque replay identity."""
    canonical = json.dumps(
        [route.tenant_id, route.channel, route.channel_account_id,
         route.provider_event_id], ensure_ascii=False, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _validate(route: RoutedInbound, event: VerifiedInbound, destination: str):
    if route.destination != destination or event.kind != InboundKind.USER_MESSAGE:
        raise ValueError("Consumer destination or inbound kind mismatch.")
    if ((route.tenant_id, route.channel, route.channel_account_id, route.provider_event_id)
            != (event.tenant_id, event.channel, event.channel_account_id,
                event.provider_event_id)):
        raise PermissionError("Inbound route/event identity mismatch.")


class RKJOAgentRouteConsumer:
    """Routes to an already configured RKJO agent via its EventBus queue."""

    def __init__(self, *, bus: EventBus, agent_name: str, queue_name: str):
        if not agent_name.strip() or not queue_name.strip():
            raise ValueError("Agent and queue configuration required.")
        self.bus = bus
        self.agent_name = agent_name
        self.queue_name = queue_name

    def deliver(self, *, route: RoutedInbound, event: VerifiedInbound) -> None:
        _validate(route, event, "agent")
        identity = route_id(route)
        message = AgentMessage(
            message_id="omnichannel:" + identity,
            correlation_id="omnichannel:" + identity,
            source="rkjo.omnichannel.route_dispatch",
            target=self.agent_name,
            message_type="omnichannel.inbound.message",
            payload={
                "provider_event_id": route.provider_event_id,
                "conversation_id": route.conversation_id,
                "channel": route.channel,
                "channel_account_id": route.channel_account_id,
                "event": dict(event.payload),
            },
            metadata={
                "tenant_id": route.tenant_id,
                "ownership_version": route.ownership_version,
                "route_id": identity,
                "origin_channel": route.channel,
                "origin_account_id": route.channel_account_id,
            },
        )
        self.bus.publish_agent_message(queue_name=self.queue_name, message=message)


@dataclass(frozen=True, slots=True)
class OperatorInboxItem:
    tenant_id: str
    conversation_id: str
    route_id: str
    channel: str
    channel_account_id: str
    provider_event_id: str
    ownership_version: int
    event_payload: dict


class PostgreSQLOperatorInbox:
    """Durable tenant-filtered operator inbox; authenticated API is a later layer."""

    def __init__(self, database_url: str):
        if not database_url or not database_url.strip():
            raise ValueError("Database URL required.")
        self.database_url = database_url

    def initialize_schema(self) -> None:
        with psycopg.connect(self.database_url) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS omni_operator_inbox (
                    tenant_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    route_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    channel_account_id TEXT NOT NULL,
                    provider_event_id TEXT NOT NULL,
                    ownership_version BIGINT NOT NULL,
                    event_payload JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(tenant_id, route_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_omni_operator_inbox_conversation
                ON omni_operator_inbox(tenant_id,conversation_id,created_at)
            """)

    def deliver(self, *, route: RoutedInbound, event: VerifiedInbound) -> None:
        _validate(route, event, "human")
        identity = route_id(route)
        payload = json.loads(json.dumps(dict(event.payload)))
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO omni_operator_inbox (
                        tenant_id,conversation_id,route_id,channel,channel_account_id,
                        provider_event_id,ownership_version,event_payload
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT DO NOTHING
                """, (
                    route.tenant_id,route.conversation_id,identity,
                    route.channel,route.channel_account_id,
                    route.provider_event_id,route.ownership_version,Jsonb(payload),
                ))
                cur.execute("""
                    SELECT conversation_id,channel,channel_account_id,
                           provider_event_id,ownership_version,event_payload
                    FROM omni_operator_inbox WHERE tenant_id=%s AND route_id=%s
                """, (route.tenant_id,identity))
                row = cur.fetchone()
                if row != (route.conversation_id,route.channel,route.channel_account_id,
                           route.provider_event_id,route.ownership_version,payload):
                    raise ValueError("Operator inbox route ID collision.")

    def list_conversation(self, *, tenant_id: str, conversation_id: str,
                          limit: int = 100) -> list[OperatorInboxItem]:
        if not tenant_id.strip() or not conversation_id.strip() or not 1 <= limit <= 500:
            raise ValueError("Tenant, conversation and valid page size required.")
        with psycopg.connect(self.database_url) as conn:
            rows = conn.execute("""
                SELECT route_id,channel,channel_account_id,provider_event_id,
                       ownership_version,event_payload
                FROM omni_operator_inbox
                WHERE tenant_id=%s AND conversation_id=%s
                ORDER BY created_at,route_id LIMIT %s
            """, (tenant_id,conversation_id,limit)).fetchall()
        return [
            OperatorInboxItem(
                tenant_id=tenant_id,conversation_id=conversation_id,route_id=row[0],
                channel=row[1],channel_account_id=row[2],provider_event_id=row[3],
                ownership_version=row[4],event_payload=row[5],
            ) for row in rows
        ]
