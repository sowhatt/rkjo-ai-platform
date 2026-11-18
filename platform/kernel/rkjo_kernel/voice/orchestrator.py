"""End-to-end realtime voice turn orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from rkjo_kernel.voice.realtime import (
    RealtimeVoiceController,
    RealtimeVoiceState,
    VoiceActivity,
)
from rkjo_kernel.voice.runtime import VoiceRuntime, VoiceTurnResult
from rkjo_kernel.voice.session import VoiceSession
from rkjo_kernel.voice.streaming import AudioChunk, VoiceStream


class AudioPlaybackPort(Protocol):
    """Provider-neutral boundary for delivering synthesized audio."""

    def play(self, result: VoiceTurnResult) -> None: ...

    def interrupt(self, *, session_id: str, tenant_id: str) -> None: ...


@dataclass(frozen=True, slots=True)
class RealtimeTurnResult:
    session: VoiceSession
    turn: VoiceTurnResult


class RealtimeVoiceOrchestrator:
    """Connect streaming, VAD, STT/agent/TTS and playback for one session."""

    def __init__(
        self,
        *,
        session: VoiceSession,
        controller: RealtimeVoiceController,
        runtime: VoiceRuntime,
        playback: AudioPlaybackPort,
    ) -> None:
        if controller.session_id != session.session_id:
            raise ValueError("Realtime controller session_id conflicts with VoiceSession.")
        if controller.tenant_id != session.tenant_id:
            raise ValueError("Realtime controller tenant_id conflicts with VoiceSession.")
        self.session = session
        self.controller = controller
        self.runtime = runtime
        self.playback = playback
        self._stream = VoiceStream(session=session)

    def accept(self, chunk: AudioChunk) -> RealtimeTurnResult | None:
        """Accept one audio chunk and execute a turn when speech ends."""
        was_agent_speaking = self.controller.state is RealtimeVoiceState.AGENT_SPEAKING
        activity = self.controller.accept(chunk)

        if (
            was_agent_speaking
            and activity.activity is VoiceActivity.SPEECH_STARTED
        ):
            self.playback.interrupt(
                session_id=self.session.session_id,
                tenant_id=self.session.tenant_id,
            )
            # A new user utterance starts after barge-in.
            self._stream = VoiceStream(session=self.session)

        if activity.activity in {
            VoiceActivity.SPEECH_STARTED,
            VoiceActivity.SPEECH_CONTINUED,
            VoiceActivity.SPEECH_ENDED,
        }:
            self._stream.push(chunk)

        if activity.activity is not VoiceActivity.SPEECH_ENDED:
            return None

        audio = self._stream.finalize()
        turn = self.runtime.execute(audio)
        self.controller.agent_started_speaking()
        self.playback.play(turn)

        completed = VoiceSession(
            session_id=self.session.session_id,
            tenant_id=self.session.tenant_id,
            mission_id=self.session.mission_id,
            trace_id=self.session.trace_id,
            state=self.session.state,
            turn_count=self.session.turn_count + 1,
            last_error=None,
        )
        self.session = completed
        self._stream = VoiceStream(session=completed)
        return RealtimeTurnResult(session=completed, turn=turn)

    def playback_finished(self) -> None:
        self.controller.agent_finished_speaking()

    def close(self) -> None:
        self.controller.close()
        self._stream.close()
