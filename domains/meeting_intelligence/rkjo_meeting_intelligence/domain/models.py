"""Core domain models for RKJO Meeting Intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


def _required(value: str, *, field_name: str) -> str:
    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} must not be empty."
        )

    return normalized


class MeetingStatus(StrEnum):
    DRAFT = "draft"
    RECORDING = "recording"
    PROCESSING = "processing"
    REVIEW = "review"
    VALIDATED = "validated"
    ARCHIVED = "archived"


class DecisionStatus(StrEnum):
    PROPOSED = "proposed"
    VALIDATED = "validated"
    CANCELLED = "cancelled"


class ActionStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class Participant:
    participant_id: str
    meeting_id: str
    tenant_id: str
    display_name: str
    role: str | None = None
    email: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "participant_id",
            "meeting_id",
            "tenant_id",
            "display_name",
        ):
            object.__setattr__(
                self,
                field_name,
                _required(
                    getattr(self, field_name),
                    field_name=field_name,
                ),
            )

        if self.role is not None:
            object.__setattr__(
                self,
                "role",
                _required(
                    self.role,
                    field_name="role",
                ),
            )

        if self.email is not None:
            object.__setattr__(
                self,
                "email",
                _required(
                    self.email,
                    field_name="email",
                ),
            )


@dataclass(frozen=True, slots=True)
class Meeting:
    meeting_id: str
    tenant_id: str
    title: str
    created_by: str
    status: MeetingStatus = MeetingStatus.DRAFT
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "meeting_id",
            "tenant_id",
            "title",
            "created_by",
        ):
            object.__setattr__(
                self,
                field_name,
                _required(
                    getattr(self, field_name),
                    field_name=field_name,
                ),
            )

        if (
            self.started_at is not None
            and self.ended_at is not None
            and self.ended_at < self.started_at
        ):
            raise ValueError(
                "ended_at must be greater than or equal to started_at."
            )


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    segment_id: str
    meeting_id: str
    tenant_id: str
    text: str
    start_seconds: float
    end_seconds: float
    speaker_id: str | None = None
    confidence: float | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "segment_id",
            "meeting_id",
            "tenant_id",
            "text",
        ):
            object.__setattr__(
                self,
                field_name,
                _required(
                    getattr(self, field_name),
                    field_name=field_name,
                ),
            )

        if self.start_seconds < 0:
            raise ValueError(
                "start_seconds must be greater than or equal to 0."
            )

        if self.end_seconds < self.start_seconds:
            raise ValueError(
                "end_seconds must be greater than or equal to start_seconds."
            )

        if self.speaker_id is not None:
            object.__setattr__(
                self,
                "speaker_id",
                _required(
                    self.speaker_id,
                    field_name="speaker_id",
                ),
            )

        if (
            self.confidence is not None
            and not 0 <= self.confidence <= 1
        ):
            raise ValueError(
                "confidence must be between 0 and 1."
            )


@dataclass(frozen=True, slots=True)
class Decision:
    decision_id: str
    meeting_id: str
    tenant_id: str
    text: str
    source_segment_id: str
    status: DecisionStatus = DecisionStatus.PROPOSED

    def __post_init__(self) -> None:
        for field_name in (
            "decision_id",
            "meeting_id",
            "tenant_id",
            "text",
            "source_segment_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _required(
                    getattr(self, field_name),
                    field_name=field_name,
                ),
            )


@dataclass(frozen=True, slots=True)
class ActionItem:
    action_id: str
    meeting_id: str
    tenant_id: str
    title: str
    source_segment_id: str
    assignee_id: str | None = None
    due_at: datetime | None = None
    status: ActionStatus = ActionStatus.TODO

    def __post_init__(self) -> None:
        for field_name in (
            "action_id",
            "meeting_id",
            "tenant_id",
            "title",
            "source_segment_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _required(
                    getattr(self, field_name),
                    field_name=field_name,
                ),
            )

        if self.assignee_id is not None:
            object.__setattr__(
                self,
                "assignee_id",
                _required(
                    self.assignee_id,
                    field_name="assignee_id",
                ),
            )
