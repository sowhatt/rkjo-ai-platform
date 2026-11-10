"""OMNI-013.2: durable conversation ownership and idempotent message routing.

The routing decision and the queued delivery to the appropriate consumer
are committed in ONE PostgreSQL transaction. Neither the agent nor the operator
is called synchronously from the inbox worker.
"""
from __future__ import annotations

import hashlib
import json
from psycopg.types.json import Jsonb
from dataclasses import dataclass
from datetime import datetime, timezone

import psycopg

from rkjo_kernel.omnichannel.contracts import ConversationMode, ConversationOwnership, ChannelResponse, ResponseOrigin
from rkjo_kernel.omnichannel.inbound import InboundKind, VerifiedInbound


@dataclass(frozen=True, slots=True)
class RoutedInbound:
    tenant_id: str
    channel: str
    channel_account_id: str
    provider_event_id: str
    conversation_id: str
    destination: str
    ownership_version: int


def _parse_message(event: VerifiedInbound) -> tuple[str, datetime]:
    if event.kind != InboundKind.USER_MESSAGE:
        raise ValueError("Only user messages can update conversation context.")
    if event.channel == "whatsapp":
        message = event.payload.get("event")
        if not isinstance(message, dict):
            raise ValueError("WhatsApp user message required.")
        sender = message.get("from")
        timestamp = message.get("timestamp")
        if not isinstance(sender, str) or not sender or not isinstance(timestamp, str):
            raise ValueError("WhatsApp sender and timestamp required.")
        try:
            occurred = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
        except (ValueError, OverflowError):
            raise ValueError("Invalid WhatsApp message timestamp.") from None
    elif event.channel == "telegram":
        message = event.payload.get("message")
        if not isinstance(message, dict):
            raise ValueError("Telegram user message required.")
        chat = message.get("chat")
        sender = str(chat.get("id")) if isinstance(chat, dict) and isinstance(chat.get("id"), int) else None
        date = message.get("date")
        if not sender or not isinstance(date, int) or isinstance(date, bool):
            raise ValueError("Telegram chat and date required.")
        try:
            occurred = datetime.fromtimestamp(date, tz=timezone.utc)
        except (ValueError, OverflowError):
            raise ValueError("Invalid Telegram message timestamp.") from None
    else:
        raise ValueError("Unsupported inbound channel.")
    # Never use a cross-channel provider identifier as a global conversation key.
    conversation_id = hashlib.sha256(
        f"{event.channel}\x00{event.channel_account_id}\x00{sender}".encode()
    ).hexdigest()
    return conversation_id, occurred


class PostgreSQLConversationRouter:
    def __init__(self, database_url: str):
        if not database_url or not database_url.strip():
            raise ValueError("Database URL required.")
        self.database_url = database_url

    def initialize_schema(self):
        with psycopg.connect(self.database_url) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS omni_conversations (
                    tenant_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    origin_channel TEXT NOT NULL,
                    mode TEXT NOT NULL CHECK (mode IN ('agent','human')),
                    assigned_operator_id TEXT,
                    ownership_version BIGINT NOT NULL DEFAULT 0,
                    last_inbound_at TIMESTAMPTZ,
                    PRIMARY KEY(tenant_id, conversation_id),
                    CHECK ((mode='human') = (assigned_operator_id IS NOT NULL))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS omni_routed_inbound (
                    tenant_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    channel_account_id TEXT NOT NULL,
                    provider_event_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    destination TEXT NOT NULL CHECK (destination IN ('agent','human')),
                    ownership_version BIGINT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(tenant_id, channel, channel_account_id, provider_event_id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS omni_route_outbox (
                    tenant_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    channel_account_id TEXT NOT NULL,
                    provider_event_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    destination TEXT NOT NULL CHECK (destination IN ('agent','human')),
                    ownership_version BIGINT NOT NULL,
                    event_payload JSONB NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending','processed','failed')),
                    attempts INTEGER NOT NULL DEFAULT 0,
                    lease_token TEXT,
                    lease_until TIMESTAMPTZ,
                    next_attempt_at TIMESTAMPTZ,
                    last_error TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(tenant_id,channel,channel_account_id,provider_event_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_omni_route_outbox_due
                ON omni_route_outbox(created_at)
                WHERE status='pending'
            """)

    def route(self, event: VerifiedInbound) -> RoutedInbound:
        conversation_id, occurred = _parse_message(event)
        key = (event.tenant_id, event.channel, event.channel_account_id, event.provider_event_id)
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                # Replays must NOT reopen WhatsApp windows or change routing.
                cur.execute("""
                    SELECT conversation_id, destination, ownership_version
                    FROM omni_routed_inbound
                    WHERE tenant_id=%s AND channel=%s AND channel_account_id=%s
                      AND provider_event_id=%s
                """, key)
                previous = cur.fetchone()
                if previous:
                    if previous[0] != conversation_id:
                        raise ValueError("Conflicting conversation identity.")
                    # A replay cannot rewrite the earlier routing decision.
                    self._queue(cur, event, conversation_id, previous[1], previous[2])
                    return RoutedInbound(*key, *previous)
                cur.execute("""
                    INSERT INTO omni_conversations
                      (tenant_id, conversation_id, origin_channel, mode)
                    VALUES (%s,%s,%s,'agent')
                    ON CONFLICT DO NOTHING
                """, (event.tenant_id, conversation_id, event.channel))
                cur.execute("""
                    SELECT origin_channel, mode, ownership_version
                    FROM omni_conversations
                    WHERE tenant_id=%s AND conversation_id=%s FOR UPDATE
                """, (event.tenant_id, conversation_id))
                row = cur.fetchone()
                if row is None or row[0] != event.channel:
                    raise PermissionError("Conversation tenant/channel mismatch.")
                mode, version = row[1], row[2]
                cur.execute("""
                    UPDATE omni_conversations
                    SET last_inbound_at=GREATEST(
                        COALESCE(last_inbound_at, %s), %s
                    )
                    WHERE tenant_id=%s AND conversation_id=%s
                """, (occurred, occurred, event.tenant_id, conversation_id))
                cur.execute("""
                    INSERT INTO omni_routed_inbound (
                        tenant_id, channel, channel_account_id,
                        provider_event_id, conversation_id,
                        destination, ownership_version
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT DO NOTHING
                    RETURNING conversation_id, destination, ownership_version
                """, (*key, conversation_id, mode, version))
                inserted = cur.fetchone()
                if inserted is None:
                    cur.execute("""
                        SELECT conversation_id, destination, ownership_version
                        FROM omni_routed_inbound
                        WHERE tenant_id=%s AND channel=%s AND channel_account_id=%s
                          AND provider_event_id=%s
                    """, key)
                    inserted = cur.fetchone()
                    if inserted[0] != conversation_id:
                        raise ValueError("Conflicting conversation identity.")
                self._queue(cur, event, conversation_id, inserted[1], inserted[2])
                return RoutedInbound(*key, *inserted)

    @staticmethod
    def _queue(cur, event: VerifiedInbound, conversation_id: str,
               destination: str, version: int) -> None:
        payload = json.loads(json.dumps(dict(event.payload)))
        key = (event.tenant_id, event.channel, event.channel_account_id, event.provider_event_id)
        cur.execute("""
            INSERT INTO omni_route_outbox (
                tenant_id, channel, channel_account_id, provider_event_id,
                conversation_id, destination, ownership_version, event_payload
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT DO NOTHING
        """, (*key, conversation_id, destination, version, Jsonb(payload)))
        cur.execute("""
            SELECT conversation_id,destination,ownership_version,event_payload
            FROM omni_route_outbox
            WHERE tenant_id=%s AND channel=%s AND channel_account_id=%s
              AND provider_event_id=%s
        """, key)
        row = cur.fetchone()
        if row != (conversation_id, destination, version, payload):
            raise ValueError("Conflicting durable route event.")

    def ownership(self, *, tenant_id: str, conversation_id: str) -> ConversationOwnership | None:
        with psycopg.connect(self.database_url) as conn:
            row = conn.execute("""
                SELECT origin_channel,mode,assigned_operator_id,
                       ownership_version,last_inbound_at
                FROM omni_conversations
                WHERE tenant_id=%s AND conversation_id=%s
            """, (tenant_id, conversation_id)).fetchone()
            if row is None:
                return None
            return ConversationOwnership(
                tenant_id=tenant_id, conversation_id=conversation_id,
                origin_channel=row[0], mode=row[1], assigned_operator_id=row[2],
                ownership_version=row[3], last_inbound_at=row[4],
            )

    def transfer(self, *, tenant_id: str, conversation_id: str,
                 expected_version: int, operator_id: str | None) -> ConversationOwnership:
        if not tenant_id or not conversation_id or expected_version < 0:
            raise ValueError("Valid conversation identity and version required.")
        if operator_id is not None and not operator_id.strip():
            raise ValueError("Operator ID cannot be blank.")
        mode = "human" if operator_id is not None else "agent"
        with psycopg.connect(self.database_url) as conn:
            row = conn.execute("""
                UPDATE omni_conversations
                SET mode=%s, assigned_operator_id=%s,
                    ownership_version=ownership_version+1
                WHERE tenant_id=%s AND conversation_id=%s
                  AND ownership_version=%s
                RETURNING origin_channel,mode,assigned_operator_id,
                          ownership_version,last_inbound_at
            """, (mode, operator_id, tenant_id, conversation_id, expected_version)).fetchone()
            if row is None:
                raise ValueError("Unknown conversation, wrong tenant or stale ownership version.")
            return ConversationOwnership(
                tenant_id=tenant_id, conversation_id=conversation_id,
                origin_channel=row[0], mode=row[1],
                assigned_operator_id=row[2], ownership_version=row[3],
                last_inbound_at=row[4],
            )

    def authorize_response(self, response: ChannelResponse) -> bool:
        """Pre-send eligibility check; sender must repeat immediately before dispatch."""
        state = self.ownership(tenant_id=response.tenant_id,
                               conversation_id=response.conversation_id)
        if state is None or state.origin_channel != response.channel:
            return False
        if state.ownership_version != response.ownership_version:
            return False
        if response.origin == ResponseOrigin.AGENT:
            return state.mode == ConversationMode.AGENT
        if response.origin == ResponseOrigin.HUMAN:
            return state.mode == ConversationMode.HUMAN
        return True


class ConversationRoutingHandler:
    """Adapter for InboundProcessingWorker; receipt events cannot enter this path."""
    def __init__(self, router: PostgreSQLConversationRouter):
        self.router = router

    def handle(self, event: VerifiedInbound) -> None:
        self.router.route(event)
