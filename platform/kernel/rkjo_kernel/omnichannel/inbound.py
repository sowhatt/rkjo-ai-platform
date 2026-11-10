"""Provider-neutral ingress routing. No webhook can bypass verification.

The adapter authenticates raw bytes before parsing/normalizing the event.
Receipt events never enter agent routing and never update last_inbound_at.
The durable inbox is a handoff ledger, not a claim that processing has finished.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol


class InboundKind(str, Enum):
    USER_MESSAGE = "user_message"
    DELIVERY_RECEIPT = "delivery_receipt"
    IGNORED = "ignored"


class InboundRoute(str, Enum):
    PENDING_MESSAGE = "pending_message"
    PENDING_RECEIPT = "pending_receipt"
    IGNORED = "ignored"
    DUPLICATE = "duplicate"


@dataclass(frozen=True, slots=True)
class VerifiedInbound:
    channel: str
    channel_account_id: str
    provider_event_id: str
    kind: InboundKind
    # Resolved only after verifying the signed webhook.
    tenant_id: str
    # A provider-neutral reference to the event stored in the inbox.
    # Raw media bytes MUST NOT be passed here.
    payload: Mapping[str, object]

    def __post_init__(self):
        if not all(isinstance(v, str) and v.strip() for v in (
            self.channel, self.channel_account_id,
            self.provider_event_id, self.tenant_id,
        )):
            raise ValueError("Tenant and provider event identity are required.")


class WebhookVerificationPort(Protocol):
    def verify_and_normalize(
        self, *, channel: str, body: bytes, headers: Mapping[str, str],
    ) -> VerifiedInbound: ...


class InboundInboxPort(Protocol):
    def accept_once(self, event: VerifiedInbound) -> bool: ...


class ChannelInboundGateway:
    """Accept durable verified events; downstream processors poll the inbox."""

    def __init__(self, *, verifier: WebhookVerificationPort, inbox: InboundInboxPort):
        self.verifier = verifier
        self.inbox = inbox

    def receive(self, *, channel: str, body: bytes, headers: Mapping[str, str]) -> InboundRoute:
        if not channel.strip() or not body:
            raise ValueError("Channel and webhook body are required.")
        # A verifier MUST reject an invalid signature or unbound account.
        event = self.verifier.verify_and_normalize(channel=channel, body=body, headers=headers)
        if event.channel != channel:
            raise PermissionError("Provider channel mismatch.")
        created = self.inbox.accept_once(event)
        if not created:
            return InboundRoute.DUPLICATE
        return {
            InboundKind.USER_MESSAGE: InboundRoute.PENDING_MESSAGE,
            InboundKind.DELIVERY_RECEIPT: InboundRoute.PENDING_RECEIPT,
            InboundKind.IGNORED: InboundRoute.IGNORED,
        }[event.kind]
