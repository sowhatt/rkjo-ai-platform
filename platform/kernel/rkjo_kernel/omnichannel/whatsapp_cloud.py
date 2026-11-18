"""OMNI-016.2: tenant-scoped WhatsApp Cloud API outbound port.

The caller MUST wrap this port with OwnershipFencedChannelAdapter and
WhatsAppWindowPolicy. This port serializes Meta payloads and validates Meta
acknowledgements. It does not retry: ambiguous provider acceptance must be
quarantined/reconciled by the existing durable delivery infrastructure.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.multimodal.notifications import Notification
from rkjo_kernel.omnichannel.channel_policy import PermanentDeliveryRejection
from rkjo_kernel.omnichannel.contracts import ChannelResponse, ResponseKind


class WhatsAppTransportError(RuntimeError):
    """Provider/network outcome uncertain. Never blindly replay a send."""


@dataclass(frozen=True)
class WhatsAppAccount:
    tenant_id: str
    channel_account_id: str
    phone_number_id: str
    access_token: str

    def __post_init__(self):
        if any(not isinstance(value, str) or not value.strip() for value in
               (self.tenant_id,self.channel_account_id,self.phone_number_id,self.access_token)):
            raise ValueError("Complete WhatsApp account credentials required.")
        if not self.phone_number_id.isdecimal():
            raise ValueError("Meta phone_number_id must be numeric.")


@dataclass(frozen=True)
class WhatsAppTemplate:
    name: str
    language_code: str

    def __post_init__(self):
        if not self.name or not self.language_code:
            raise ValueError("Template name and language required.")


class WhatsAppAccountRegistry(Protocol):
    def resolve(self, *, tenant_id: str, channel_account_id: str) -> WhatsAppAccount: ...


class WhatsAppTemplateRegistry(Protocol):
    def resolve(self, *, tenant_id: str, channel_account_id: str,
                template_id: str) -> WhatsAppTemplate: ...


class WhatsAppHTTPTransport(Protocol):
    def post(self, *, url: str, token: str, payload: dict) -> tuple[int, dict]: ...


class UrllibWhatsAppHTTPTransport:
    def __init__(self, *, timeout_seconds: float = 7.0):
        if not 0 < timeout_seconds <= 9:
            raise ValueError("Timeout must fit ownership lock statement timeout.")
        self.timeout_seconds = timeout_seconds

    def post(self, *, url: str, token: str, payload: dict) -> tuple[int, dict]:
        request = Request(
            url,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(65537)
                status = response.status
        except HTTPError as exc:
            status = exc.code
            raw = exc.read(65537)
        except (URLError, TimeoutError, OSError) as exc:
            raise WhatsAppTransportError("WhatsApp transport result is uncertain.") from exc
        if len(raw) > 65536:
            raise WhatsAppTransportError("WhatsApp response too large.")
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise WhatsAppTransportError("Invalid WhatsApp JSON response.") from exc
        if not isinstance(body, dict):
            raise WhatsAppTransportError("Invalid WhatsApp response object.")
        return status, body


class WhatsAppCloudAPIAdapter:
    def __init__(
        self, *, accounts: WhatsAppAccountRegistry,
        templates: WhatsAppTemplateRegistry,
        transport: WhatsAppHTTPTransport | None = None,
        graph_version: str = "v23.0",
    ):
        if not graph_version.startswith("v") or not graph_version[1:].replace(".", "").isdecimal():
            raise ValueError("Invalid Graph API version.")
        self.accounts = accounts
        self.templates = templates
        self.transport = transport or UrllibWhatsAppHTTPTransport()
        self.graph_version = graph_version

    def send(self, *, notification: Notification, message: AgentMessage) -> str:
        raw = message.payload.get("omnichannel_response")
        if not isinstance(raw, dict):
            raise ValueError("Explicit omnichannel_response required.")
        response = ChannelResponse.model_validate(raw)
        if (response.channel != "whatsapp" or notification.channel != "whatsapp"
                or response.tenant_id != notification.tenant_id
                or response.notification_id != notification.notification_id
                or response.recipient_ref != notification.recipient_ref
                or message.metadata.get("tenant_id") != response.tenant_id):
            raise PermissionError("Unbound WhatsApp message identity.")
        account = self.accounts.resolve(
            tenant_id=response.tenant_id,
            channel_account_id=response.channel_account_id,
        )
        if (account.tenant_id != response.tenant_id
                or account.channel_account_id != response.channel_account_id):
            raise PermissionError("WhatsApp account registry cross-tenant mismatch.")
        payload: dict = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": response.recipient_ref,
        }
        if response.kind == ResponseKind.TEXT:
            payload.update(type="text", text={"preview_url": False, "body": response.text})
        elif response.kind == ResponseKind.TEMPLATE:
            template_id = response.fallback_template_id
            if not template_id:
                raise PermanentDeliveryRejection("Template reference missing.")
            template = self.templates.resolve(
                tenant_id=response.tenant_id,
                channel_account_id=response.channel_account_id,
                template_id=template_id,
            )
            if not template.name or not template.language_code:
                raise PermanentDeliveryRejection("Template configuration incomplete.")
            payload.update(
                type="template",
                template={"name": template.name, "language": {"code": template.language_code}},
            )
        else:
            raise PermanentDeliveryRejection(
                "Unsupported WhatsApp response kind; explicit serialization required."
            )
        try:
            status, body = self.transport.post(
                url=f"https://graph.facebook.com/{self.graph_version}/{account.phone_number_id}/messages",
                token=account.access_token, payload=payload,
            )
        except WhatsAppTransportError:
            raise
        except Exception as exc:
            raise WhatsAppTransportError("WhatsApp transport raised unexpectedly.") from exc
        if status < 200 or status >= 300:
            # Even 429/5xx cannot safely be replayed after an ambiguous call.
            raise WhatsAppTransportError(f"WhatsApp HTTP response {status}; manual reconciliation required.")
        messages = body.get("messages")
        if not isinstance(messages, list) or len(messages) != 1 or not isinstance(messages[0], dict):
            raise WhatsAppTransportError("WhatsApp acceptance acknowledgement missing.")
        provider_id = messages[0].get("id")
        if not isinstance(provider_id, str) or not provider_id.startswith("wamid.") or len(provider_id) <= 6:
            raise WhatsAppTransportError("Invalid WhatsApp provider message ID.")
        return provider_id
