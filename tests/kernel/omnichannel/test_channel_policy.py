"""OMNI-014.4: WhatsApp channel policy and terminal notification handling."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from rkjo_kernel.omnichannel.channel_policy import WhatsAppWindowPolicy, PermanentDeliveryRejection
from rkjo_kernel.omnichannel.contracts import ChannelResponse, ResponseKind, ResponseOrigin
from rkjo_kernel.multimodal.notifications import (
    Notification, NotificationDeliveryWorker, NotificationStatus,
)
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.omnichannel.guarded_delivery import ObsoleteConversationResponse


NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


def response(kind=ResponseKind.TEXT, *, template=None):
    return ChannelResponse(
        notification_id="n1", tenant_id="tenant-1",
        conversation_id="c1", channel="whatsapp",
        channel_account_id="phone-1", recipient_ref="customer-1",
        origin=ResponseOrigin.AGENT, ownership_version=0,
        kind=kind, text="Hello" if kind == ResponseKind.TEXT else None,
        fallback_template_id=template,
    )


class Templates:
    def __init__(self, approved=True):
        self.approved = approved
        self.calls = []

    def is_approved(self, *, tenant_id, channel_account_id, template_id):
        self.calls.append((tenant_id, channel_account_id, template_id))
        return self.approved


def policy(last, *, approved=True):
    templates = Templates(approved)
    obj = WhatsAppWindowPolicy(
        last_inbound=lambda _: last, templates=templates, now=lambda: NOW,
    )
    return obj, templates


def test_recent_verified_inbound_allows_freeform():
    obj, templates = policy(NOW - timedelta(minutes=2))
    obj.check(response())
    assert templates.calls == []


@pytest.mark.parametrize("last", [
    None, NOW - timedelta(hours=24), NOW - timedelta(days=2),
    NOW + timedelta(seconds=5),
])
def test_expired_missing_or_future_inbound_rejects_freeform(last):
    obj, _ = policy(last)
    with pytest.raises(PermanentDeliveryRejection):
        obj.check(response())


def test_approved_template_allowed_outside_window():
    obj, templates = policy(None)
    obj.check(response(ResponseKind.TEMPLATE, template="approved-1"))
    assert templates.calls == [("tenant-1", "phone-1", "approved-1")]


def test_unapproved_template_denied_and_fallback_does_not_bypass_window():
    obj, templates = policy(None, approved=False)
    with pytest.raises(PermanentDeliveryRejection):
        obj.check(response(ResponseKind.TEMPLATE, template="unapproved"))
    with pytest.raises(PermanentDeliveryRejection):
        obj.check(response(template="unapproved"))


def test_template_kind_requires_template_reference():
    with pytest.raises(ValueError, match="Template response"):
        response(ResponseKind.TEMPLATE)


class Store:
    def __init__(self, notification, message):
        self.claim = (notification, message)
        self.terminal = []
        self.failed = []
        self.sent = []

    def claim_due(self, **kwargs):
        value, self.claim = self.claim, None
        return value

    def mark_terminal(self, **kwargs):
        self.terminal.append(kwargs)

    def mark_failed(self, **kwargs):
        self.failed.append(kwargs)

    def mark_sent(self, **kwargs):
        self.sent.append(kwargs)


class Adapter:
    def __init__(self, exc=None):
        self.exc = exc

    def send(self, **kwargs):
        if self.exc is not None:
            raise self.exc
        return "wamid-1"


def store():
    n = Notification(
        notification_id="n1", tenant_id="tenant-1", job_id="j1",
        channel="whatsapp", recipient_ref="customer-1",
        status=NotificationStatus.IN_FLIGHT,
        attempts=1, lease_token="lease-1",
    )
    m = AgentMessage(source="s",target="t",payload={"job_id":"j1"})
    return Store(n, m)


@pytest.mark.parametrize("error", [
    PermanentDeliveryRejection("Expired"),
    ObsoleteConversationResponse("Taken over"),
])
def test_terminal_denials_are_not_retried(error):
    data = store()
    worker = NotificationDeliveryWorker(
        store=data, adapters={"whatsapp": Adapter(error)},
    )
    assert worker.run_once(now=NOW)
    assert len(data.terminal) == 1
    assert data.failed == []
    assert data.sent == []


def test_generic_provider_exception_remains_retryable():
    data = store()
    worker = NotificationDeliveryWorker(
        store=data, adapters={"whatsapp": Adapter(RuntimeError("Temporary"))},
    )
    assert worker.run_once(now=NOW)
    assert data.terminal == []
    assert len(data.failed) == 1


def test_successful_send_marks_existing_notification_sent():
    data = store()
    worker = NotificationDeliveryWorker(store=data, adapters={"whatsapp": Adapter()})
    assert worker.run_once(now=NOW)
    assert data.terminal == []
    assert data.failed == []
    assert data.sent[0]["provider_ref"] == "wamid-1"
