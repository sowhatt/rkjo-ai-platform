"""Transcription jobs and provider contracts for Meeting Intelligence."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol


class TranscriptionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TranscriptionJob:
    job_id: str
    tenant_id: str
    meeting_id: str
    asset_id: str
    status: TranscriptionStatus
    created_at: datetime
    updated_at: datetime
    error: str | None = None

    def __post_init__(self) -> None:
        for name in ("job_id", "tenant_id", "meeting_id", "asset_id"):
            value = getattr(self, name).strip()
            if not value:
                raise ValueError(f"{name} must not be empty.")
            object.__setattr__(self, name, value)

        if self.error is not None:
            error = self.error.strip()
            object.__setattr__(self, "error", error or None)

    @classmethod
    def queued(
        cls,
        *,
        job_id: str,
        tenant_id: str,
        meeting_id: str,
        asset_id: str,
    ) -> "TranscriptionJob":
        now = datetime.now(UTC)
        return cls(
            job_id=job_id,
            tenant_id=tenant_id,
            meeting_id=meeting_id,
            asset_id=asset_id,
            status=TranscriptionStatus.QUEUED,
            created_at=now,
            updated_at=now,
        )

    def transition(
        self,
        status: TranscriptionStatus,
        *,
        error: str | None = None,
    ) -> "TranscriptionJob":
        allowed = {
            TranscriptionStatus.QUEUED: {TranscriptionStatus.RUNNING, TranscriptionStatus.FAILED},
            TranscriptionStatus.RUNNING: {TranscriptionStatus.COMPLETED, TranscriptionStatus.FAILED},
            TranscriptionStatus.COMPLETED: set(),
            TranscriptionStatus.FAILED: set(),
        }
        if status not in allowed[self.status]:
            raise ValueError(
                f"Invalid transcription transition: {self.status.value} -> {status.value}."
            )
        return replace(
            self,
            status=status,
            updated_at=datetime.now(UTC),
            error=error,
        )


@dataclass(frozen=True, slots=True)
class STTSegment:
    text: str
    start_seconds: float
    end_seconds: float
    speaker_id: str | None = None
    confidence: float | None = None


class STTProvider(Protocol):
    def transcribe(
        self,
        *,
        content: bytes,
        filename: str,
        content_type: str,
    ) -> list[STTSegment]:
        """Return timestamped transcript segments for one media object."""
        ...


class TranscriptionDispatcher(Protocol):
    def dispatch(self, job: TranscriptionJob) -> None:
        """Queue one transcription job for asynchronous processing."""
        ...
