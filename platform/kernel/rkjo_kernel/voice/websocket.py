"""WebSocket-neutral wire adapter for RKJO live voice."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from rkjo_kernel.voice.live import LiveVoiceEvent, LiveVoiceEventType
from rkjo_kernel.voice.streaming import AudioChunk


class WebSocketPeerPort(Protocol):
    """Minimal synchronous socket boundary implemented by API/framework adapters."""

    def send_json(self, payload: Mapping[str, Any]) -> None: ...

    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class WebSocketAudioMessage:
    data: bytes
    sequence: int
    mime_type: str
    tenant_id: str
    session_id: str
    mission_id: str | None = None
    trace_id: str | None = None
    is_final: bool = False

    def to_chunk(self) -> AudioChunk:
        return AudioChunk(
            data=self.data,
            sequence=self.sequence,
            mime_type=self.mime_type,
            tenant_id=self.tenant_id,
            session_id=self.session_id,
            mission_id=self.mission_id,
            trace_id=self.trace_id,
            is_final=self.is_final,
        )


class VoiceWebSocketCodec:
    """Strict JSON wire codec. Audio bytes use base64 on the transport boundary."""

    @staticmethod
    def decode_audio(payload: Mapping[str, Any]) -> AudioChunk:
        if payload.get("type") != "audio.chunk":
            raise ValueError("Expected audio.chunk WebSocket message.")
        encoded = payload.get("data")
        if not isinstance(encoded, str) or not encoded:
            raise ValueError("audio.chunk requires base64 data.")
        try:
            data = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise ValueError("audio.chunk contains invalid base64 data.") from exc

        sequence = payload.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool):
            raise ValueError("audio.chunk sequence must be an integer.")

        message = WebSocketAudioMessage(
            data=data,
            sequence=sequence,
            mime_type=str(payload.get("mime_type") or ""),
            tenant_id=str(payload.get("tenant_id") or ""),
            session_id=str(payload.get("session_id") or ""),
            mission_id=payload.get("mission_id"),
            trace_id=payload.get("trace_id"),
            is_final=payload.get("is_final") is True,
        )
        return message.to_chunk()

    @staticmethod
    def encode_event(event: LiveVoiceEvent) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": event.event_type.value,
            "session_id": event.session_id,
            "tenant_id": event.tenant_id,
            "mission_id": event.mission_id,
            "trace_id": event.trace_id,
        }
        if event.sequence is not None:
            payload["sequence"] = event.sequence
        if event.transcript is not None:
            payload["transcript"] = {
                "text": event.transcript.text,
                "language": event.transcript.language,
                "confidence": event.transcript.confidence,
            }
        if event.audio is not None:
            payload["audio"] = {
                "data": base64.b64encode(event.audio.data).decode("ascii"),
                "mime_type": event.audio.mime_type,
            }
        if event.error is not None:
            payload["error"] = event.error
        if event.metadata:
            payload["metadata"] = dict(event.metadata)
        return payload


class VoiceWebSocketTransport:
    """LiveVoiceTransportPort implementation over a framework-neutral peer."""

    def __init__(self, *, peer: WebSocketPeerPort) -> None:
        self.peer = peer
        self._closed = False

    def send(self, event: LiveVoiceEvent) -> None:
        if self._closed:
            raise RuntimeError("Voice WebSocket transport is closed.")
        self.peer.send_json(VoiceWebSocketCodec.encode_event(event))

    def close(self, *, session_id: str, tenant_id: str) -> None:
        if self._closed:
            return
        self._closed = True
        self.peer.close()
