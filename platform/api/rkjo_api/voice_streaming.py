"""Async WebSocket sink for outbound realtime voice audio."""

from __future__ import annotations

import asyncio
import base64
from typing import Any, Awaitable, Callable, Mapping

from rkjo_kernel.voice.streaming import AudioChunk


class AsyncWebSocketAudioSink:
    """Bridge synchronous playback callbacks to an async WebSocket sender.

    send() is intentionally non-blocking: ordered payloads are serialized by
    one internal queue consumer.
    """

    def __init__(
        self,
        *,
        send_json: Callable[[Mapping[str, Any]], Awaitable[None]],
    ) -> None:
        self._send_json = send_json
        self._queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(self._run())

    def send(self, chunk: AudioChunk) -> None:
        if self._worker is None:
            raise RuntimeError("WebSocket audio sink is not started.")
        self._queue.put_nowait({
            "type": "audio.chunk",
            "data": base64.b64encode(chunk.data).decode("ascii"),
            "sequence": chunk.sequence,
            "mime_type": chunk.mime_type,
            "tenant_id": chunk.tenant_id,
            "session_id": chunk.session_id,
            "mission_id": chunk.mission_id,
            "trace_id": chunk.trace_id,
            "is_final": chunk.is_final,
        })

    def interrupt(self, *, session_id: str, tenant_id: str) -> None:
        if self._worker is None:
            raise RuntimeError("WebSocket audio sink is not started.")
        self._queue.put_nowait({
            "type": "audio.interrupted",
            "session_id": session_id,
            "tenant_id": tenant_id,
        })

    async def drain(self) -> None:
        await self._queue.join()

    async def close(self) -> None:
        if self._worker is None:
            return
        await self._queue.put(None)
        await self._worker
        self._worker = None

    async def _run(self) -> None:
        while True:
            payload = await self._queue.get()
            try:
                if payload is None:
                    return
                await self._send_json(payload)
            finally:
                self._queue.task_done()
