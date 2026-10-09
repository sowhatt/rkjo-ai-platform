"""OMNI-001..009 contract invariants, no provider side effects."""
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from rkjo_kernel.omnichannel.contracts import (
    MediaAttachment, MediaStatus, UnifiedMessageEnvelope, DeliveryStatusEvent,
    DeliveryStatus, ConversationOwnership, ConversationMode, ChannelResponse,
    ResponseKind, ResponseOrigin,
)

NOW = datetime.now(timezone.utc)


def envelope(**kwargs):
    data = dict(
        message_id="internal-1", external_message_id="provider-1",
        tenant_id="tenant-a", conversation_id="conversation-a",
        channel="whatsapp", channel_account_id="business-a",
        external_sender_id="user-a", text="describe this",
        received_at=NOW, correlation_id="correlation-a",
    )
    data.update(kwargs)
    return UnifiedMessageEnvelope(**data)


def test_text_and_validated_media_share_one_envelope():
    msg = envelope(attachments=[
        MediaAttachment(attachment_id="a", status=MediaStatus.ACCEPTED, artifact_ref="safe-tenant-a-1"),
    ])
    assert msg.should_invoke_agent
    assert msg.accepted_media_refs == ("safe-tenant-a-1",)


def test_rejected_only_media_does_not_invoke_agent():
    msg = envelope(text=None, attachments=[
        MediaAttachment(attachment_id="a", status=MediaStatus.REJECTED, rejection_code="malware"),
    ])
    assert msg.should_invoke_agent is False
    assert msg.accepted_media_refs == ()


def test_text_continues_after_media_rejection():
    msg = envelope(attachments=[
        MediaAttachment(attachment_id="a", status=MediaStatus.REJECTED, rejection_code="too_large"),
    ])
    assert msg.should_invoke_agent


@pytest.mark.parametrize("attachment", [
    dict(attachment_id="a", status="accepted", artifact_ref=None),
    dict(attachment_id="a", status="rejected", artifact_ref="raw", rejection_code="infected"),
    dict(attachment_id="a", status="rejected", rejection_code=None),
])
def test_no_unvalidated_media_refs(attachment):
    with pytest.raises(ValidationError):
        MediaAttachment(**attachment)


def test_envelope_rejects_duplicate_attachments_and_empty_content():
    with pytest.raises(ValidationError):
        envelope(text=None, attachments=[])
    with pytest.raises(ValidationError):
        envelope(attachments=[
            MediaAttachment(attachment_id="a", status="rejected", rejection_code="size"),
            MediaAttachment(attachment_id="a", status="rejected", rejection_code="size"),
        ])


def test_delivery_receipt_requires_timezone_and_never_implies_new_inbound():
    receipt = DeliveryStatusEvent(
        event_id="e", tenant_id="tenant-a", channel="whatsapp",
        channel_account_id="business-a", external_message_id="provider-out-1",
        status=DeliveryStatus.READ, occurred_at=NOW, received_at=NOW,
    )
    assert "last_inbound_at" not in receipt.model_fields
    with pytest.raises(ValidationError):
        receipt.model_copy(update={"occurred_at": NOW.replace(tzinfo=None)}).model_validate(
            receipt.model_dump() | {"occurred_at": NOW.replace(tzinfo=None)}
        )


def test_conversation_human_mode_requires_operator_and_version():
    with pytest.raises(ValidationError):
        ConversationOwnership(tenant_id="t", conversation_id="c", origin_channel="telegram",
                              mode=ConversationMode.HUMAN)
    ownership = ConversationOwnership(
        tenant_id="t", conversation_id="c", origin_channel="telegram",
        mode="human", assigned_operator_id="operator-1", ownership_version=3,
    )
    assert ownership.ownership_version == 3


def test_channel_response_requires_content_and_origin_version():
    with pytest.raises(ValidationError):
        ChannelResponse(notification_id="n", tenant_id="t", conversation_id="c",
                        channel="telegram", channel_account_id="a", recipient_ref="r",
                        origin=ResponseOrigin.AGENT, ownership_version=0,
                        kind=ResponseKind.LIST, text="Choose")
    response = ChannelResponse(notification_id="n", tenant_id="t", conversation_id="c",
                               channel="telegram", channel_account_id="a", recipient_ref="r",
                               origin=ResponseOrigin.AGENT, ownership_version=0,
                               kind=ResponseKind.LIST, text="Choose", options=["A", "B"])
    assert response.options == ["A", "B"]
