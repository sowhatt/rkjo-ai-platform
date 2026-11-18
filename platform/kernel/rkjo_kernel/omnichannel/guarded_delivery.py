"""OMNI-014.3: ownership-fenced adapter for the existing RKJO delivery worker.

Wrap an existing ChannelDeliveryPort. The conversation row is locked
FOR SHARE until the provider call finishes: operator takeover (UPDATE)
cannot commit between authorization and send. Keep network timeouts short.
A provider accepted send followed by DB crash can still be repeated: ensure
provider-side idempotency where available.

This adapter is enabled ONLY for messages carrying the explicit
omnichannel_response contract. Other multimodal notifications remain with
their existing adapters; never silently bypass this guard for such messages.
"""
from __future__ import annotations

from typing import Protocol

import psycopg

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.multimodal.notifications import ChannelDeliveryPort, Notification
from rkjo_kernel.omnichannel.contracts import ChannelResponse, ResponseOrigin


class ObsoleteConversationResponse(PermissionError):
    """A queued response is no longer authorized; must not reach the provider."""


class ChannelPolicyPort(Protocol):
    def check(self, response: ChannelResponse) -> None:
        """Raise on policy rejection (e.g. WhatsApp 24h rule)."""


class AllowAllChannelPolicy:
    """Test-only policy. Do not configure for production provider traffic."""

    def check(self, response: ChannelResponse) -> None:
        return None


class OwnershipFencedChannelAdapter:
    """Existing delivery port decorator with tenant/account/version fencing.

    The provider call takes place under a PostgreSQL shared row lock.
    The takeover uses an UPDATE, and must wait for the in-flight call.
    """

    def __init__(
        self, *, database_url: str, downstream: ChannelDeliveryPort,
        policy: ChannelPolicyPort,
        delivery_ledger=None,
    ):
        if not database_url or not database_url.strip():
            raise ValueError("Database URL required.")
        self.database_url = database_url
        self.downstream = downstream
        self.policy = policy
        self.delivery_ledger = delivery_ledger

    def send(self, *, notification: Notification, message: AgentMessage) -> str:
        raw = message.payload.get("omnichannel_response")
        if not isinstance(raw, dict):
            raise ValueError("Missing omnichannel_response contract.")
        response = ChannelResponse.model_validate(raw)
        if (notification.notification_id != response.notification_id
                or notification.tenant_id != response.tenant_id
                or notification.channel != response.channel
                or notification.recipient_ref != response.recipient_ref
                or message.metadata.get("tenant_id") != response.tenant_id):
            raise PermissionError("Notification/response tenant or routing mismatch.")
        if response.origin not in (ResponseOrigin.AGENT, ResponseOrigin.HUMAN):
            raise PermissionError("System messages require a separate authorization policy.")
        # The trusted route must be persisted: never trust an account ID
        # supplied solely by an unverified generated response.
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = 10000")
                cur.execute("""
                    SELECT origin_channel,mode,assigned_operator_id,ownership_version
                    FROM omni_conversations
                    WHERE tenant_id=%s AND conversation_id=%s
                    FOR SHARE
                """, (response.tenant_id,response.conversation_id))
                state = cur.fetchone()
                if state is None:
                    raise ObsoleteConversationResponse("Conversation does not exist.")
                origin_channel, mode, operator_id, version = state
                if (origin_channel != response.channel
                        or version != response.ownership_version
                        or mode != response.origin.value):
                    raise ObsoleteConversationResponse("Conversation ownership is obsolete.")
                cur.execute("""
                    SELECT event_payload FROM omni_route_outbox
                    WHERE tenant_id=%s AND conversation_id=%s
                      AND channel=%s AND channel_account_id=%s
                    ORDER BY created_at DESC LIMIT 1
                """, (
                    response.tenant_id,response.conversation_id,
                    response.channel,response.channel_account_id,
                ))
                route_row = cur.fetchone()
                if route_row is None:
                    raise PermissionError("Unbound origin channel account.")
                provider_event = route_row[0].get("event", {})
                if response.channel == "whatsapp":
                    expected_recipient = provider_event.get("from")
                elif response.channel == "telegram":
                    chat = route_row[0].get("message", {}).get("chat", {})
                    expected_recipient = str(chat.get("id")) if chat.get("id") is not None else None
                else:
                    raise PermissionError("Unsupported provider channel.")
                if (not isinstance(expected_recipient, str) or
                        response.recipient_ref != expected_recipient):
                    raise PermissionError("Response recipient does not match verified inbound.")
                if response.origin == ResponseOrigin.HUMAN:
                    sender_operator = message.metadata.get("operator_id")
                    if (not isinstance(sender_operator,str)
                            or sender_operator != operator_id):
                        raise PermissionError("Assigned operator identity required.")
                # This policy is injected and is fail-closed in production:
                # it must enforce WhatsApp conversational window/template rules.
                self.policy.check(response)
                provider_ref = self.downstream.send(
                    notification=notification, message=message,
                )
                if not isinstance(provider_ref,str) or not provider_ref.strip():
                    raise ValueError("Provider did not acknowledge an outbound message.")
                if self.delivery_ledger is not None:
                    self.delivery_ledger.register_sent(
                        tenant_id=response.tenant_id,
                        notification_id=response.notification_id,
                        channel=response.channel,
                        channel_account_id=response.channel_account_id,
                        provider_message_id=provider_ref,
                    )
                return provider_ref
