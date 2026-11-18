"""Provider-neutral voice contracts for RKJO."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class AudioInput:
    data: bytes
    mime_type: str
    tenant_id: str
    mission_id: str | None = None
    trace_id: str | None = None
    language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.data:
            raise ValueError("Audio input cannot be empty.")
        if not self.mime_type.strip().lower().startswith("audio/"):
            raise ValueError("Audio input requires an audio/* MIME type.")
        if not self.tenant_id.strip():
            raise ValueError("Audio input tenant_id cannot be empty.")


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    tenant_id: str
    mission_id: str | None = None
    trace_id: str | None = None
    language: str | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("Transcript text cannot be empty.")
        if not self.tenant_id.strip():
            raise ValueError("Transcript tenant_id cannot be empty.")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Transcript confidence must be between 0 and 1.")


@dataclass(frozen=True, slots=True)
class SpeechRequest:
    text: str
    tenant_id: str
    mission_id: str | None = None
    trace_id: str | None = None
    voice: str | None = None
    language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("Speech request text cannot be empty.")
        if not self.tenant_id.strip():
            raise ValueError("Speech request tenant_id cannot be empty.")


@dataclass(frozen=True, slots=True)
class AudioOutput:
    data: bytes
    mime_type: str
    tenant_id: str
    mission_id: str | None = None
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.data:
            raise ValueError("Audio output cannot be empty.")
        if not self.mime_type.strip().lower().startswith("audio/"):
            raise ValueError("Audio output requires an audio/* MIME type.")
        if not self.tenant_id.strip():
            raise ValueError("Audio output tenant_id cannot be empty.")
