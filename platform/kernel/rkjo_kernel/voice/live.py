"""Provider-neutral live transport contracts for RKJO Voice."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from rkjo_kernel.voice.models import AudioOutput, Transcript
from rkjo_kernel.voice.streaming import AudioChunk


class LiveVoiceEventType(str, Enum):
    SESSION_OPENED = "session_opened"
    AUDIO_IN = "audio_in"
    TRANSCRIPT = "transcript"
    THINKING = "thinking"
    AUDIO_OUT = "audio_out"
    INTERRUPTED = "interrupted"
    ERROR = "error"
    SESSION_CLOSED = "session_closed"


@dataclass(frozen=True, slots=True)
class LiveVoiceEvent:
    event_type: LiveVoiceEventType
    session_id: str
    tenant_id: str
    mission_id: str | None = None
    trace_id: str | None = None
    sequence: int | None = None
    transcript: Transcript | None = None
    audio: AudioOutput | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.session_id.strip() or not self.tenant_id.strip():
            raise ValueError("Live voice event requires session_id and tenant_id.")
        if self.sequence is not None and self.sequence < 0:
            raise ValueError("Live voice event sequence cannot be negative.")


class LiveVoiceTransportPort(Protocol):
    """Bidirectional transport boundary; WebSocket/WebRTC adapters implement it."""

    def send(self, event: LiveVoiceEvent) -> None: ...

    def close(self, *, session_id: str, tenant_id: str) -> None: ...


class LiveVoiceSession:
    """Fail-closed event bridge around a live transport."""

    def __init__(
        self,
        *,
        session_id: str,
        tenant_id: str,
        mission_id: str | None,
        trace_id: str | None,
        transport: LiveVoiceTransportPort,
    ) -> None:
        if not session_id.strip() or not tenant_id.strip():
            raise ValueError("Live voice session requires session_id and tenant_id.")
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.mission_id = mission_id
        self.trace_id = trace_id
        self.transport = transport
        self._closed = False
        self._emit(LiveVoiceEventType.SESSION_OPENED)

    def audio_received(self, chunk: AudioChunk) -> None:
        self._ensure_open()
        self._validate_chunk(chunk)
        self._emit(LiveVoiceEventType.AUDIO_IN, sequence=chunk.sequence)

    def transcript_ready(self, transcript: Transcript) -> None:
        self._ensure_open()
        self._validate_identity(
            transcript.tenant_id, transcript.mission_id, transcript.trace_id
        )
        self._emit(LiveVoiceEventType.TRANSCRIPT, transcript=transcript)

    def thinking(self) -> None:
        self._ensure_open()
        self._emit(LiveVoiceEventType.THINKING)

    def audio_ready(self, audio: AudioOutput) -> None:
        self._ensure_open()
        self._validate_identity(audio.tenant_id, audio.mission_id, audio.trace_id)
        self._emit(LiveVoiceEventType.AUDIO_OUT, audio=audio)

    def interrupted(self, *, sequence: int | None = None) -> None:
        self._ensure_open()
        self._emit(LiveVoiceEventType.INTERRUPTED, sequence=sequence)

    def error(self, error: Exception | str) -> None:
        self._ensure_open()
        self._emit(LiveVoiceEventType.ERROR, error=str(error))

    def close(self) -> None:
        if self._closed:
            return
        self._emit(LiveVoiceEventType.SESSION_CLOSED)
        self._closed = True
        self.transport.close(session_id=self.session_id, tenant_id=self.tenant_id)

    def _validate_chunk(self, chunk: AudioChunk) -> None:
        if chunk.session_id != self.session_id:
            raise ValueError("Audio chunk session_id conflicts with live session.")
        self._validate_identity(chunk.tenant_id, chunk.mission_id, chunk.trace_id)

    def _validate_identity(
        self,
        tenant_id: str,
        mission_id: str | None,
        trace_id: str | None,
    ) -> None:
        if tenant_id != self.tenant_id:
            raise ValueError("Live voice tenant_id conflict.")
        if mission_id != self.mission_id:
            raise ValueError("Live voice mission_id conflict.")
        if trace_id != self.trace_id:
            raise ValueError("Live voice trace_id conflict.")

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Live voice session is closed.")

    def _emit(self, event_type: LiveVoiceEventType, **kwargs: Any) -> None:
        self.transport.send(LiveVoiceEvent(
            event_type=event_type,
            session_id=self.session_id,
            tenant_id=self.tenant_id,
            mission_id=self.mission_id,
            trace_id=self.trace_id,
            **kwargs,
        ))
