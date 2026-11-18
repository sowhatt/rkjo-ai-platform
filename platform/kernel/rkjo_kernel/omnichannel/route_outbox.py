"""OMNI-014.1: lease-based agent/operator routing outbox dispatcher.

Handlers are ports to an existing Policy Engine / Operator Inbox transport;
they must use event identity as their idempotency key. No provider is invoked
in this layer. An ownership version mismatch discards obsolete delivery.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import uuid4

import psycopg

from rkjo_kernel.omnichannel.inbound import InboundKind, VerifiedInbound
from rkjo_kernel.omnichannel.conversation_router import RoutedInbound, PostgreSQLConversationRouter


@dataclass(frozen=True, slots=True)
class ClaimedRoute:
    route: RoutedInbound
    event: VerifiedInbound
    lease_token: str
    attempt: int


class RouteConsumerPort(Protocol):
    def deliver(self, *, route: RoutedInbound, event: VerifiedInbound) -> None: ...


class PostgreSQLRouteOutbox:
    def __init__(self, database_url: str, *, max_attempts: int = 4):
        if not database_url or not database_url.strip() or max_attempts < 1:
            raise ValueError("Database URL and positive max_attempts required.")
        self.database_url = database_url
        self.max_attempts = max_attempts

    @staticmethod
    def _key(route: RoutedInbound):
        return (route.tenant_id, route.channel, route.channel_account_id, route.provider_event_id)

    @staticmethod
    def _check_time(now: datetime):
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Timezone-aware now required.")

    def claim_due(self, *, now: datetime, lease_seconds: int = 30) -> ClaimedRoute | None:
        self._check_time(now)
        if lease_seconds < 1:
            raise ValueError("Positive lease required.")
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE omni_route_outbox
                    SET status='failed', lease_token=NULL, lease_until=NULL,
                        last_error='MaxAttemptsExceeded'
                    WHERE status='pending' AND attempts >= %s
                      AND (lease_until IS NULL OR lease_until<=%s)
                """, (self.max_attempts, now))
                cur.execute("""
                    SELECT tenant_id,channel,channel_account_id,provider_event_id,
                           conversation_id,destination,ownership_version,event_payload,attempts
                    FROM omni_route_outbox
                    WHERE status='pending' AND attempts < %s
                      AND (lease_until IS NULL OR lease_until<=%s)
                      AND (next_attempt_at IS NULL OR next_attempt_at<=%s)
                    ORDER BY created_at,provider_event_id
                    LIMIT 1 FOR UPDATE SKIP LOCKED
                """, (self.max_attempts,now,now))
                row = cur.fetchone()
                if row is None:
                    return None
                route = RoutedInbound(*row[:7])
                event = VerifiedInbound(
                    tenant_id=route.tenant_id, channel=route.channel,
                    channel_account_id=route.channel_account_id,
                    provider_event_id=route.provider_event_id,
                    kind=InboundKind.USER_MESSAGE, payload=row[7],
                )
                token = uuid4().hex
                cur.execute("""
                    UPDATE omni_route_outbox
                    SET attempts=attempts+1,lease_token=%s,lease_until=%s,
                        next_attempt_at=NULL
                    WHERE tenant_id=%s AND channel=%s AND channel_account_id=%s
                      AND provider_event_id=%s
                """, (token,now+timedelta(seconds=lease_seconds),*self._key(route)))
                return ClaimedRoute(route,event,token,row[8]+1)

    def finish(self, claim: ClaimedRoute, *, obsolete: bool = False) -> None:
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE omni_route_outbox SET status='processed',
                        lease_token=NULL,lease_until=NULL,
                        next_attempt_at=NULL,last_error=%s
                    WHERE tenant_id=%s AND channel=%s AND channel_account_id=%s
                      AND provider_event_id=%s AND lease_token=%s AND status='pending'
                """, ("ObsoleteOwnership" if obsolete else None,
                      *self._key(claim.route),claim.lease_token))
                if cur.rowcount != 1:
                    raise ValueError("Stale routing lease.")

    def fail(self, claim: ClaimedRoute, *, now: datetime,
             error: str, retry_delay_seconds: int = 5) -> None:
        self._check_time(now)
        if not error or retry_delay_seconds < 0:
            raise ValueError("Invalid routing retry.")
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE omni_route_outbox
                    SET status=CASE WHEN attempts >= %s THEN 'failed' ELSE 'pending' END,
                        lease_token=NULL,lease_until=NULL,
                        next_attempt_at=CASE WHEN attempts >= %s THEN NULL ELSE %s END,
                        last_error=%s
                    WHERE tenant_id=%s AND channel=%s AND channel_account_id=%s
                      AND provider_event_id=%s AND lease_token=%s AND status='pending'
                """, (self.max_attempts,self.max_attempts,
                      now+timedelta(seconds=retry_delay_seconds),error[:200],
                      *self._key(claim.route),claim.lease_token))
                if cur.rowcount != 1:
                    raise ValueError("Stale routing lease.")


class RoutingDispatchWorker:
    def __init__(self, *, store: PostgreSQLRouteOutbox,
                 conversations: PostgreSQLConversationRouter,
                 agent: RouteConsumerPort, operator: RouteConsumerPort,
                 lease_seconds: int = 30):
        self.store = store
        self.conversations = conversations
        self.agent = agent
        self.operator = operator
        self.lease_seconds = lease_seconds

    def run_once(self, *, now: datetime) -> bool:
        claim = self.store.claim_due(now=now, lease_seconds=self.lease_seconds)
        if claim is None:
            return False
        route = claim.route
        state = self.conversations.ownership(
            tenant_id=route.tenant_id, conversation_id=route.conversation_id,
        )
        if (state is None or state.ownership_version != route.ownership_version
                or state.mode.value != route.destination
                or state.origin_channel != route.channel):
            self.store.finish(claim, obsolete=True)
            return True
        try:
            consumer = self.agent if route.destination == "agent" else self.operator
            consumer.deliver(route=route, event=claim.event)
        except Exception as exc:
            self.store.fail(claim, now=now, error=type(exc).__name__)
            return True
        self.store.finish(claim)
        return True
