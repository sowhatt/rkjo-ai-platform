"""Application bridge from WebSocket audio to RKJO realtime voice runtime."""

from __future__ import annotations

from typing import Protocol

from rkjo_kernel.voice.live import LiveVoiceSession
from rkjo_kernel.voice.orchestrator import RealtimeVoiceOrchestrator, VoiceTurnResult
from rkjo_kernel.voice.realtime import RealtimeVoiceState
from rkjo_kernel.voice.streaming import AudioChunk


class VoiceLiveBridge:
    """Bridge authenticated inbound chunks to runtime and outbound live events."""

    def __init__(
        self,
        *,
        live: LiveVoiceSession,
        orchestrator: RealtimeVoiceOrchestrator,
    ) -> None:
        if live.session_id != orchestrator.session.session_id:
            raise ValueError("Live session_id conflicts with realtime orchestrator.")
        if live.tenant_id != orchestrator.session.tenant_id:
            raise ValueError("Live tenant_id conflicts with realtime orchestrator.")
        if live.mission_id != orchestrator.session.mission_id:
            raise ValueError("Live mission_id conflicts with realtime orchestrator.")
        if live.trace_id != orchestrator.session.trace_id:
            raise ValueError("Live trace_id conflicts with realtime orchestrator.")
        self.live = live
        self.orchestrator = orchestrator

    async def on_audio(self, chunk: AudioChunk) -> None:
        self.live.audio_received(chunk)
        was_speaking = (
            self.orchestrator.controller.state
            is RealtimeVoiceState.AGENT_SPEAKING
        )
        result = self.orchestrator.accept(chunk)

        if (
            was_speaking
            and self.orchestrator.controller.state
            is RealtimeVoiceState.USER_SPEAKING
        ):
            self.live.interrupted(sequence=chunk.sequence)

        if result is None:
            return

        self.live.transcript_ready(result.turn.transcript)
        self.live.thinking()
        self.live.audio_ready(result.turn.audio)
