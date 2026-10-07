"""Streaming synthesized-audio delivery for realtime RKJO Voice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from rkjo_kernel.voice.runtime import VoiceTurnResult
from rkjo_kernel.voice.streaming import AudioChunk


class AudioChunkSinkPort(Protocol):
    def send(self, chunk: AudioChunk) -> None: ...

    def interrupt(self, *, session_id: str, tenant_id: str) -> None: ...


@dataclass(slots=True)
class StreamingAudioPlayback:
    """Adapt a complete TTS result into ordered transport audio chunks."""

    sink: AudioChunkSinkPort
    chunk_size: int = 4096

    def __post_init__(self) -> None:
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive.")

    def play(self, result: VoiceTurnResult) -> None:
        audio = result.audio
        session_id = audio.metadata.get("voice_session_id")
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("Audio output requires voice_session_id metadata.")

        parts = [
            audio.data[offset: offset + self.chunk_size]
            for offset in range(0, len(audio.data), self.chunk_size)
        ]
        for sequence, data in enumerate(parts):
            self.sink.send(AudioChunk(
                data=data,
                sequence=sequence,
                mime_type=audio.mime_type,
                tenant_id=audio.tenant_id,
                session_id=session_id,
                mission_id=audio.mission_id,
                trace_id=audio.trace_id,
                is_final=sequence == len(parts) - 1,
            ))

    def interrupt(self, *, session_id: str, tenant_id: str) -> None:
        self.sink.interrupt(session_id=session_id, tenant_id=tenant_id)
