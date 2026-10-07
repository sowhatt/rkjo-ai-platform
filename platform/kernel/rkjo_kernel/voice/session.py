"""Conversation session state for RKJO Voice Runtime."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from rkjo_kernel.voice.models import AudioInput
from rkjo_kernel.voice.runtime import VoiceRuntime, VoiceTurnResult


class VoiceSessionState(str, Enum):
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    CLOSED = "closed"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class VoiceSession:
    session_id: str
    tenant_id: str
    mission_id: str | None = None
    trace_id: str | None = None
    state: VoiceSessionState = VoiceSessionState.LISTENING
    turn_count: int = 0
    last_error: str | None = None

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("Voice session_id cannot be empty.")
        if not self.tenant_id.strip():
            raise ValueError("Voice session tenant_id cannot be empty.")
        if self.turn_count < 0:
            raise ValueError("Voice session turn_count cannot be negative.")


class VoiceSessionEngine:
    """Coordinate deterministic multi-turn voice session state."""

    def __init__(self, *, runtime: VoiceRuntime) -> None:
        self.runtime = runtime

    def execute_turn(
        self,
        session: VoiceSession,
        audio: AudioInput,
    ) -> tuple[VoiceSession, VoiceTurnResult]:
        self._validate_turn(session, audio)
        thinking = replace(
            session,
            state=VoiceSessionState.THINKING,
            last_error=None,
        )
        try:
            result = self.runtime.execute(audio)
            speaking = replace(
                thinking,
                state=VoiceSessionState.SPEAKING,
            )
            completed = replace(
                speaking,
                state=VoiceSessionState.LISTENING,
                turn_count=session.turn_count + 1,
            )
            return completed, result
        except Exception as exc:
            # Return is impossible while preserving the original exception,
            # so callers retain their last durable session and can explicitly
            # mark/report failure at their persistence boundary.
            raise

    @staticmethod
    def close(session: VoiceSession) -> VoiceSession:
        if session.state is VoiceSessionState.CLOSED:
            return session
        return replace(session, state=VoiceSessionState.CLOSED)

    @staticmethod
    def mark_error(session: VoiceSession, error: Exception | str) -> VoiceSession:
        return replace(
            session,
            state=VoiceSessionState.ERROR,
            last_error=str(error),
        )

    @staticmethod
    def _validate_turn(session: VoiceSession, audio: AudioInput) -> None:
        if session.state is not VoiceSessionState.LISTENING:
            raise RuntimeError(
                "Voice session must be LISTENING before accepting audio."
            )
        if audio.tenant_id != session.tenant_id:
            raise ValueError("AudioInput tenant_id conflicts with VoiceSession.")
        if audio.mission_id != session.mission_id:
            raise ValueError("AudioInput mission_id conflicts with VoiceSession.")
        if audio.trace_id != session.trace_id:
            raise ValueError("AudioInput trace_id conflicts with VoiceSession.")
