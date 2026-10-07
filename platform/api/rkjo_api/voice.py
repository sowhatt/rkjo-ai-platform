"""FastAPI WebSocket gateway primitives for RKJO Voice."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Mapping, Protocol

from rkjo_kernel.voice.streaming import AudioChunk
from rkjo_kernel.voice.websocket import VoiceWebSocketCodec


class AsyncWebSocketPort(Protocol):
    async def accept(self) -> None: ...
    async def receive_json(self) -> Mapping[str, Any]: ...
    async def send_json(self, payload: Mapping[str, Any]) -> None: ...
    async def close(self, code: int = 1000) -> None: ...


class VoiceChunkHandlerPort(Protocol):
    async def __call__(self, chunk: AudioChunk) -> None: ...


class VoiceWebSocketGateway:
    """Authenticate identity at the API boundary and dispatch audio chunks.

    Framework connection lifecycle stays here; STT/TTS/providers remain in the
    kernel/runtime layer.
    """

    def __init__(
        self,
        *,
        websocket: AsyncWebSocketPort,
        tenant_id: str,
        session_id: str,
        mission_id: str | None,
        trace_id: str | None,
        on_audio: Callable[[AudioChunk], Awaitable[None]],
    ) -> None:
        if not tenant_id.strip() or not session_id.strip():
            raise ValueError("Voice gateway requires tenant_id and session_id.")
        self.websocket = websocket
        self.tenant_id = tenant_id
        self.session_id = session_id
        self.mission_id = mission_id
        self.trace_id = trace_id
        self.on_audio = on_audio

    async def run(self) -> None:
        await self.websocket.accept()
        try:
            while True:
                payload = await self.websocket.receive_json()
                chunk = VoiceWebSocketCodec.decode_audio(payload)
                self._validate_identity(chunk)
                await self.on_audio(chunk)
        except StopAsyncIteration:
            await self.websocket.close(code=1000)
        except Exception as exc:
            await self.websocket.send_json({
                "type": "error",
                "session_id": self.session_id,
                "tenant_id": self.tenant_id,
                "error": str(exc),
            })
            await self.websocket.close(code=1008)

    def _validate_identity(self, chunk: AudioChunk) -> None:
        if chunk.tenant_id != self.tenant_id:
            raise ValueError("WebSocket audio tenant_id conflicts with authenticated tenant.")
        if chunk.session_id != self.session_id:
            raise ValueError("WebSocket audio session_id conflicts with gateway session.")
        if chunk.mission_id != self.mission_id:
            raise ValueError("WebSocket audio mission_id conflicts with gateway session.")
        if chunk.trace_id != self.trace_id:
            raise ValueError("WebSocket audio trace_id conflicts with gateway session.")
