"""OMNI-014.4 WhatsApp policy: verified 24h window and approved templates.

Template approval must come from a trusted tenant/account-scoped registry;
the response alone cannot claim approval. The downstream provider adapter
must serialize ResponseKind.TEMPLATE as a WhatsApp template, never free text.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable, Protocol

from rkjo_kernel.omnichannel.contracts import ChannelResponse, ResponseKind


class PermanentDeliveryRejection(PermissionError):
    """Reject permanently, without retries."""


class ApprovedTemplatePort(Protocol):
    def is_approved(self, *, tenant_id: str, channel_account_id: str,
                    template_id: str) -> bool: ...


class WhatsAppWindowPolicy:
    def __init__(self, *, last_inbound: Callable[[ChannelResponse], datetime | None],
                 templates: ApprovedTemplatePort,
                 now: Callable[[], datetime] | None = None):
        self.last_inbound = last_inbound
        self.templates = templates
        self.now = now or (lambda: datetime.now(timezone.utc))

    def check(self, response: ChannelResponse) -> None:
        if response.channel != "whatsapp":
            raise PermanentDeliveryRejection("WhatsApp policy cannot authorize another channel.")
        current = self.now()
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("Policy clock must be timezone-aware.")
        if response.kind == ResponseKind.TEMPLATE:
            template = response.fallback_template_id
            if not template or not self.templates.is_approved(
                tenant_id=response.tenant_id,
                channel_account_id=response.channel_account_id,
                template_id=template,
            ):
                raise PermanentDeliveryRejection("WhatsApp template not approved for this tenant/account.")
            return
        last = self.last_inbound(response)
        if last is None or last.tzinfo is None or last.utcoffset() is None:
            raise PermanentDeliveryRejection("No verified inbound time for WhatsApp free-form reply.")
        # Future-dated messages never open the customer service window.
        if last > current or current - last >= timedelta(hours=24):
            raise PermanentDeliveryRejection("WhatsApp 24-hour window expired; approved template required.")
