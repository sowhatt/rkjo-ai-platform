"""Streaming foundations for RKJO voice sessions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from rkjo_kernel.voice.models import AudioInput
from rkjo_kernel.voice.session import VoiceSession


@dataclass(frozen=True, slots=True)
class AudioChunk:
    data: bytes
    sequence: int
    mime_type: str
    tenant_id: str
    session_id: str
    mission_id: str | None = None
    trace_id: str | None = None
    is_final: bool = False

    def __post_init__(self) -> None:
        if not self.data:
            raise ValueError("Audio chunk cannot be empty.")
        if self.sequence < 0:
            raise ValueError("Audio chunk sequence cannot be negative.")
        if not self.mime_type.strip().lower().startswith("audio/"):
            raise ValueError("Audio chunk requires an audio/* MIME type.")
        if not self.tenant_id.strip() or not self.session_id.strip():
            raise ValueError("Audio chunk requires tenant_id and session_id.")


class VoiceStreamEventType(str, Enum):
    OPENED = "opened"
    AUDIO_RECEIVED = "audio_received"
    FINALIZED = "finalized"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class VoiceStreamEvent:
    event_type: VoiceStreamEventType
    session_id: str
    tenant_id: str
    sequence: int | None = None


class VoiceStreamSink(Protocol):
    def publish(self, event: VoiceStreamEvent) -> None: ...


class VoiceStream:
    """Accumulate ordered chunks for one authenticated voice session."""

    def __init__(self, *, session: VoiceSession, sink: VoiceStreamSink | None = None) -> None:
        self.session = session
        self.sink = sink
        self._chunks: list[AudioChunk] = []
        self._closed = False
        self._finalized = False
        self._emit(VoiceStreamEventType.OPENED)

    def push(self, chunk: AudioChunk) -> None:
        if self._closed:
            raise RuntimeError("Voice stream is closed.")
        if self._finalized:
            raise RuntimeError("Voice stream is already finalized.")
        self._validate_identity(chunk)
        expected = len(self._chunks)
        if chunk.sequence != expected:
            raise ValueError(f"Expected audio chunk sequence {expected}.")
        self._chunks.append(chunk)
        self._emit(VoiceStreamEventType.AUDIO_RECEIVED, chunk.sequence)
        if chunk.is_final:
            self._finalized = True

    def finalize(self) -> AudioInput:
        if self._closed:
            raise RuntimeError("Voice stream is closed.")
        if not self._chunks:
            raise ValueError("Cannot finalize an empty voice stream.")
        if not self._finalized:
            self._finalized = True
        mime_type = self._chunks[0].mime_type
        if any(chunk.mime_type != mime_type for chunk in self._chunks):
            raise ValueError("All audio chunks must use the same MIME type.")
        self._emit(VoiceStreamEventType.FINALIZED)
        return AudioInput(
            data=b"".join(chunk.data for chunk in self._chunks),
            mime_type=mime_type,
            tenant_id=self.session.tenant_id,
            mission_id=self.session.mission_id,
            trace_id=self.session.trace_id,
            metadata={"voice_session_id": self.session.session_id},
        )

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._emit(VoiceStreamEventType.CLOSED)

    def _validate_identity(self, chunk: AudioChunk) -> None:
        if chunk.session_id != self.session.session_id:
            raise ValueError("Audio chunk session_id conflicts with VoiceSession.")
        if chunk.tenant_id != self.session.tenant_id:
            raise ValueError("Audio chunk tenant_id conflicts with VoiceSession.")
        if chunk.mission_id != self.session.mission_id:
            raise ValueError("Audio chunk mission_id conflicts with VoiceSession.")
        if chunk.trace_id != self.session.trace_id:
            raise ValueError("Audio chunk trace_id conflicts with VoiceSession.")

    def _emit(self, event_type: VoiceStreamEventType, sequence: int | None = None) -> None:
        if self.sink is not None:
            self.sink.publish(VoiceStreamEvent(
                event_type=event_type,
                session_id=self.session.session_id,
                tenant_id=self.session.tenant_id,
                sequence=sequence,
            ))
