"""OMNI-012: authenticated WhatsApp batch decomposition, without partial acceptance.

An entire webhook is checked against the same Meta application secret.
Each event is tenant-resolved independently; mixed accounts with different
app secrets are rejected. No event is stored before verification completes.
"""
from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from rkjo_kernel.omnichannel.inbound import InboundKind, VerifiedInbound, InboundRoute
from rkjo_kernel.omnichannel.provider_security import (
    ProviderAccountRegistry, ProviderWebhookVerifier, _json_object,
)


class WhatsAppBatchVerifier:
    def __init__(self, *, accounts: ProviderAccountRegistry, max_events: int = 100):
        if max_events < 1:
            raise ValueError("max_events must be positive.")
        self.accounts = accounts
        self.max_events = max_events

    def verify_and_normalize_batch(
        self, *, channel: str, body: bytes, headers: Mapping[str, str],
    ) -> tuple[VerifiedInbound, ...]:
        if channel != "whatsapp" or not body:
            raise ValueError("Expected nonempty WhatsApp webhook.")
        signature = {k.lower(): v for k, v in headers.items()}.get("x-hub-signature-256", "")
        if not signature.startswith("sha256=") or len(signature) != 71:
            raise PermissionError("Missing Meta webhook signature.")
        document = _json_object(body)
        entries = document.get("entry")
        if not isinstance(entries, list) or not entries:
            raise ValueError("WhatsApp entry list required.")
        events: list[VerifiedInbound] = []
        app_secret: str | None = None
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("changes"), list):
                raise ValueError("Invalid WhatsApp entry.")
            for change in entry["changes"]:
                value = change.get("value") if isinstance(change, dict) else None
                metadata = value.get("metadata") if isinstance(value, dict) else None
                account_id = metadata.get("phone_number_id") if isinstance(metadata, dict) else None
                if not isinstance(account_id, str) or not account_id:
                    raise ValueError("WhatsApp phone_number_id missing.")
                account = self.accounts.resolve(channel="whatsapp", channel_account_id=account_id)
                if app_secret is not None and app_secret != account.credential:
                    raise PermissionError("WhatsApp batch spans separate Meta app secrets.")
                app_secret = account.credential
                messages = value.get("messages", [])
                statuses = value.get("statuses", [])
                if not isinstance(messages, list) or not isinstance(statuses, list):
                    raise ValueError("Invalid WhatsApp event arrays.")
                for kind, items in ((InboundKind.USER_MESSAGE, messages),
                                    (InboundKind.DELIVERY_RECEIPT, statuses)):
                    for item in items:
                        if not isinstance(item, dict):
                            raise ValueError("Malformed WhatsApp event.")
                        external_id = item.get("id")
                        if not isinstance(external_id, str) or not external_id:
                            raise ValueError("WhatsApp event ID missing.")
                        if kind == InboundKind.USER_MESSAGE:
                            event_id = "message:" + external_id
                        else:
                            status, timestamp = item.get("status"), item.get("timestamp")
                            if not isinstance(status, str) or not isinstance(timestamp, str):
                                raise ValueError("WhatsApp status and timestamp required.")
                            event_id = f"status:{external_id}:{status}:{timestamp}"
                        events.append(VerifiedInbound(
                            channel="whatsapp", channel_account_id=account_id,
                            tenant_id=account.tenant_id, provider_event_id=event_id,
                            kind=kind, payload={"event": item},
                        ))
                        if len(events) > self.max_events:
                            raise ValueError("Webhook event count exceeds limit.")
        if not events or app_secret is None:
            raise ValueError("Webhook contains no supported messages or statuses.")
        expected = "sha256=" + hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise PermissionError("Invalid Meta HMAC signature.")
        return tuple(events)


class BatchInboxPort:
    def accept_batch(self, events: Sequence[VerifiedInbound]) -> list[bool]:
        raise NotImplementedError


class BatchInboundGateway:
    def __init__(self, *, verifier: WhatsAppBatchVerifier, inbox: BatchInboxPort):
        self.verifier = verifier
        self.inbox = inbox

    def receive_batch(self, *, channel: str, body: bytes, headers: Mapping[str, str]) -> tuple[InboundRoute, ...]:
        events = self.verifier.verify_and_normalize_batch(channel=channel, body=body, headers=headers)
        created = self.inbox.accept_batch(events)
        if len(created) != len(events):
            raise RuntimeError("Inbox batch result length mismatch.")
        routes = {
            InboundKind.USER_MESSAGE: InboundRoute.PENDING_MESSAGE,
            InboundKind.DELIVERY_RECEIPT: InboundRoute.PENDING_RECEIPT,
            InboundKind.IGNORED: InboundRoute.IGNORED,
        }
        return tuple(routes[e.kind] if is_new else InboundRoute.DUPLICATE
                     for e, is_new in zip(events, created))
