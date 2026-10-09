"""Omnichannel V2.1 boundary contracts; no I/O or provider-specific assumptions."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class MediaStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class MediaAttachment(StrictContract):
    attachment_id: str = Field(min_length=1)
    external_media_id: str | None = None
    status: MediaStatus
    artifact_ref: str | None = None
    rejection_code: str | None = None

    @model_validator(mode="after")
    def check_outcome(self):
        if self.status == MediaStatus.ACCEPTED:
            if not self.artifact_ref or self.rejection_code:
                raise ValueError("Accepted media require validated artifact_ref only.")
        elif self.artifact_ref is not None or not self.rejection_code:
            raise ValueError("Rejected media require rejection_code and no artifact_ref.")
        return self


class UnifiedMessageEnvelope(StrictContract):
    schema_version: Literal["1.0"] = "1.0"
    message_id: str = Field(min_length=1)
    external_message_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    channel_account_id: str = Field(min_length=1)
    external_sender_id: str = Field(min_length=1)
    text: str | None = None
    attachments: list[MediaAttachment] = Field(default_factory=list)
    received_at: datetime
    correlation_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_message(self):
        if not self.text or not self.text.strip():
            if not self.attachments:
                raise ValueError("Message must contain text or attachments.")
        if len({a.attachment_id for a in self.attachments}) != len(self.attachments):
            raise ValueError("Attachment identifiers must be unique.")
        if self.received_at.utcoffset() is None:
            raise ValueError("Received timestamp must be timezone aware.")
        return self

    @property
    def accepted_media_refs(self) -> tuple[str, ...]:
        return tuple(a.artifact_ref for a in self.attachments if a.status == MediaStatus.ACCEPTED)

    @property
    def should_invoke_agent(self) -> bool:
        return bool(self.text and self.text.strip()) or bool(self.accepted_media_refs)


class DeliveryStatus(str, Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class DeliveryStatusEvent(StrictContract):
    schema_version: Literal["1.0"] = "1.0"
    event_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    channel_account_id: str = Field(min_length=1)
    external_message_id: str = Field(min_length=1)
    notification_id: str | None = None
    status: DeliveryStatus
    occurred_at: datetime
    received_at: datetime
    failure_code: str | None = None

    @model_validator(mode="after")
    def validate_receipt(self):
        if self.occurred_at.utcoffset() is None or self.received_at.utcoffset() is None:
            raise ValueError("Delivery timestamps must be timezone aware.")
        if self.status != DeliveryStatus.FAILED and self.failure_code is not None:
            raise ValueError("Only failed receipts can carry a failure code.")
        return self


class ConversationMode(str, Enum):
    AGENT = "agent"
    HUMAN = "human"


class ConversationOwnership(StrictContract):
    tenant_id: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    origin_channel: str = Field(min_length=1)
    mode: ConversationMode = ConversationMode.AGENT
    assigned_operator_id: str | None = None
    ownership_version: int = Field(default=0, ge=0)
    last_inbound_at: datetime | None = None

    @model_validator(mode="after")
    def check_owner(self):
        if self.mode == ConversationMode.HUMAN and not self.assigned_operator_id:
            raise ValueError("Human mode requires an assigned operator.")
        if self.mode == ConversationMode.AGENT and self.assigned_operator_id is not None:
            raise ValueError("Agent mode cannot have an assigned operator.")
        if self.last_inbound_at is not None and self.last_inbound_at.utcoffset() is None:
            raise ValueError("last_inbound_at must be timezone aware.")
        return self


class ResponseOrigin(str, Enum):
    AGENT = "agent"
    HUMAN = "human"
    SYSTEM = "system"


class ResponseKind(str, Enum):
    TEXT = "text"
    BUTTONS = "buttons"
    LIST = "list"
    MEDIA = "media"


class ChannelResponse(StrictContract):
    notification_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    channel_account_id: str = Field(min_length=1)
    recipient_ref: str = Field(min_length=1)
    origin: ResponseOrigin
    ownership_version: int = Field(ge=0)
    kind: ResponseKind
    text: str | None = None
    media_ref: str | None = None
    fallback_template_id: str | None = None
    options: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_response(self):
        if self.kind == ResponseKind.MEDIA and not self.media_ref:
            raise ValueError("Media response requires a validated media reference.")
        if self.kind in (ResponseKind.TEXT, ResponseKind.BUTTONS, ResponseKind.LIST) and not (self.text and self.text.strip()):
            raise ValueError("Text/list/button responses require text.")
        if self.kind in (ResponseKind.LIST, ResponseKind.BUTTONS) and not self.options:
            raise ValueError("Interactive responses require options.")
        return self
