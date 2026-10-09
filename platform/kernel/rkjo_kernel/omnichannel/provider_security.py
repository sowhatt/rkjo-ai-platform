"""Authenticated provider webhook boundary for RKJO OMNI-011.

Webhook accounts are resolved from trusted configuration, never from a claimed
tenant in the payload. Provider parsing is deliberately separate from auth.
No network calls are performed in this module.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Mapping, Protocol

from rkjo_kernel.omnichannel.inbound import (
    InboundKind,
    VerifiedInbound,
)


@dataclass(frozen=True, slots=True)
class ProviderAccount:
    channel: str
    channel_account_id: str
    tenant_id: str
    credential: str

    def __post_init__(self):
        if not all(isinstance(v, str) and v.strip() for v in (
            self.channel, self.channel_account_id, self.tenant_id, self.credential
        )):
            raise ValueError("Provider account binding and credential required.")


class ProviderAccountRegistry(Protocol):
    def resolve(self, *, channel: str, channel_account_id: str) -> ProviderAccount: ...


class StaticProviderAccountRegistry:
    """For tests / explicit deployments. Never resolve tenant from webhook body."""
    def __init__(self, accounts: list[ProviderAccount]):
        self._accounts = {}
        for account in accounts:
            key = (account.channel, account.channel_account_id)
            if key in self._accounts:
                raise ValueError("Duplicate provider account binding.")
            self._accounts[key] = account

    def resolve(self, *, channel: str, channel_account_id: str) -> ProviderAccount:
        try:
            return self._accounts[(channel, channel_account_id)]
        except KeyError:
            raise PermissionError("Unknown provider account.") from None


class ProviderWebhookVerifier:
    """Verified event normalization for WhatsApp Cloud and Telegram bot webhooks.

    WhatsApp: HMAC-SHA256 computed over unmodified raw HTTP body, then account
    resolved from payload and verified against configured credentials.
    A single Meta App Secret should be configured for the accounts belonging to
    the same Meta application. An unknown account is always rejected.

    Telegram: secret token header checked against a provisioned account picked
    from a trusted endpoint binding (not the incoming JSON payload).
    """

    def __init__(self, *, accounts: ProviderAccountRegistry,
                 telegram_endpoint_account_id: str | None = None):
        self.accounts = accounts
        self.telegram_endpoint_account_id = telegram_endpoint_account_id

    def verify_and_normalize(
        self, *, channel: str, body: bytes, headers: Mapping[str, str],
    ) -> VerifiedInbound:
        if channel not in ("whatsapp", "telegram"):
            raise PermissionError("Unsupported webhook channel.")
        if not body:
            raise ValueError("Empty webhook.")
        lowered = {key.lower(): value for key, value in headers.items()}
        if channel == "telegram":
            account_id = self.telegram_endpoint_account_id
            if not account_id:
                raise PermissionError("Telegram webhook endpoint is not bound to a bot.")
            account = self.accounts.resolve(channel="telegram", channel_account_id=account_id)
            provided = lowered.get("x-telegram-bot-api-secret-token", "")
            if not hmac.compare_digest(provided.encode(), account.credential.encode()):
                raise PermissionError("Invalid Telegram webhook secret.")
            document = _json_object(body)
            event_id = document.get("update_id")
            if not isinstance(event_id, int) or isinstance(event_id, bool) or event_id < 0:
                raise ValueError("Telegram update_id required.")
            kind = InboundKind.USER_MESSAGE if "message" in document else InboundKind.IGNORED
            return VerifiedInbound(channel="telegram", channel_account_id=account_id,
                                   tenant_id=account.tenant_id, provider_event_id=str(event_id),
                                   kind=kind, payload=document)

        # Meta signature must be checked before processing payload contents.
        signature = lowered.get("x-hub-signature-256", "")
        if not signature.startswith("sha256=") or len(signature) != 71:
            raise PermissionError("Missing WhatsApp HMAC signature.")
        # Account IDs are extracted only to SELECT a trusted secret, never to
        # accept identity. An attacker cannot forge a valid signature.
        document = _json_object(body)
        entry = document.get("entry")
        if not isinstance(entry, list) or len(entry) != 1:
            raise ValueError("Expected one WhatsApp entry.")
        changes = entry[0].get("changes") if isinstance(entry[0], dict) else None
        if not isinstance(changes, list) or len(changes) != 1:
            raise ValueError("Expected one WhatsApp change.")
        value = changes[0].get("value") if isinstance(changes[0], dict) else None
        metadata = value.get("metadata") if isinstance(value, dict) else None
        account_id = metadata.get("phone_number_id") if isinstance(metadata, dict) else None
        if not isinstance(account_id, str) or not account_id:
            raise ValueError("WhatsApp phone_number_id missing.")
        account = self.accounts.resolve(channel="whatsapp", channel_account_id=account_id)
        digest = hmac.new(account.credential.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, "sha256=" + digest):
            raise PermissionError("Invalid WhatsApp webhook signature.")
        messages = value.get("messages") or []
        statuses = value.get("statuses") or []
        if (not isinstance(messages, list) or not isinstance(statuses, list)
                or len(messages) + len(statuses) != 1):
            # A batch must be split into individual canonical events by a
            # separate, authenticated parser before it can be registered.
            raise ValueError("WhatsApp batches require explicit event splitting.")
        item = messages[0] if messages else statuses[0]
        event_id = item.get("id") if isinstance(item, dict) else None
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("WhatsApp event identifier missing.")
        if messages:
            kind = InboundKind.USER_MESSAGE
            unique_id = "message:" + event_id
        else:
            kind = InboundKind.DELIVERY_RECEIPT
            # Several status updates share the same outbound message ID.
            status = item.get("status")
            timestamp = item.get("timestamp")
            if not isinstance(status, str) or not isinstance(timestamp, str):
                raise ValueError("WhatsApp status and timestamp required.")
            unique_id = f"status:{event_id}:{status}:{timestamp}"
        return VerifiedInbound(
            channel="whatsapp", channel_account_id=account_id,
            tenant_id=account.tenant_id, provider_event_id=unique_id,
            kind=kind, payload={"value": value, "event": item},
        )


def _json_object(body: bytes) -> dict:
    try:
        value = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("Invalid JSON webhook body.") from None
    if not isinstance(value, dict):
        raise ValueError("Webhook payload must be an object.")
    return value
