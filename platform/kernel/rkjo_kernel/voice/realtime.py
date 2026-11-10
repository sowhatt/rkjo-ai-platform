"""Realtime interaction primitives for RKJO Voice."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from rkjo_kernel.voice.streaming import AudioChunk


class VoiceActivity(str, Enum):
    SPEECH_STARTED = "speech_started"
    SPEECH_CONTINUED = "speech_continued"
    SPEECH_ENDED = "speech_ended"
    SILENCE = "silence"


@dataclass(frozen=True, slots=True)
class VoiceActivityEvent:
    activity: VoiceActivity
    session_id: str
    tenant_id: str
    sequence: int


class VoiceActivityDetectorPort(Protocol):
    def detect(self, chunk: AudioChunk) -> VoiceActivity: ...


class RealtimeVoiceState(str, Enum):
    LISTENING = "listening"
    USER_SPEAKING = "user_speaking"
    THINKING = "thinking"
    AGENT_SPEAKING = "agent_speaking"
    INTERRUPTED = "interrupted"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class RealtimeVoiceEvent:
    state: RealtimeVoiceState
    session_id: str
    tenant_id: str
    sequence: int | None = None
    interrupted: bool = False


class RealtimeVoiceEventSink(Protocol):
    def publish(self, event: RealtimeVoiceEvent) -> None: ...


class RealtimeVoiceController:
    """State controller for VAD and barge-in.

    Transport, audio playback and provider-specific VAD stay outside this
    controller. It only owns deterministic interaction state.
    """

    def __init__(
        self,
        *,
        session_id: str,
        tenant_id: str,
        vad: VoiceActivityDetectorPort,
        sink: RealtimeVoiceEventSink | None = None,
    ) -> None:
        if not session_id.strip() or not tenant_id.strip():
            raise ValueError("Realtime voice requires session_id and tenant_id.")
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.vad = vad
        self.sink = sink
        self.state = RealtimeVoiceState.LISTENING

    def accept(self, chunk: AudioChunk) -> VoiceActivityEvent:
        self._validate_chunk(chunk)
        if self.state is RealtimeVoiceState.CLOSED:
            raise RuntimeError("Realtime voice session is closed.")

        activity = self.vad.detect(chunk)
        event = VoiceActivityEvent(
            activity=activity,
            session_id=self.session_id,
            tenant_id=self.tenant_id,
            sequence=chunk.sequence,
        )

        if activity is VoiceActivity.SPEECH_STARTED:
            interrupted = self.state is RealtimeVoiceState.AGENT_SPEAKING
            self.state = (
                RealtimeVoiceState.INTERRUPTED
                if interrupted
                else RealtimeVoiceState.USER_SPEAKING
            )
            self._emit(chunk.sequence, interrupted=interrupted)
            if interrupted:
                # After signalling cancellation of agent playback, ownership
                # immediately returns to the user.
                self.state = RealtimeVoiceState.USER_SPEAKING
        elif activity is VoiceActivity.SPEECH_CONTINUED:
            if self.state is not RealtimeVoiceState.USER_SPEAKING:
                self.state = RealtimeVoiceState.USER_SPEAKING
                self._emit(chunk.sequence)
        elif activity is VoiceActivity.SPEECH_ENDED:
            self.state = RealtimeVoiceState.THINKING
            self._emit(chunk.sequence)

        return event

    def agent_started_speaking(self) -> None:
        if self.state not in {
            RealtimeVoiceState.THINKING,
            RealtimeVoiceState.LISTENING,
        }:
            raise RuntimeError("Agent cannot start speaking from current state.")
        self.state = RealtimeVoiceState.AGENT_SPEAKING
        self._emit()

    def agent_finished_speaking(self) -> None:
        if self.state is not RealtimeVoiceState.AGENT_SPEAKING:
            raise RuntimeError("Agent is not speaking.")
        self.state = RealtimeVoiceState.LISTENING
        self._emit()

    def close(self) -> None:
        self.state = RealtimeVoiceState.CLOSED
        self._emit()

    def _validate_chunk(self, chunk: AudioChunk) -> None:
        if chunk.session_id != self.session_id:
            raise ValueError("Audio chunk session_id conflicts with realtime session.")
        if chunk.tenant_id != self.tenant_id:
            raise ValueError("Audio chunk tenant_id conflicts with realtime session.")

    def _emit(self, sequence: int | None = None, *, interrupted: bool = False) -> None:
        if self.sink is not None:
            self.sink.publish(RealtimeVoiceEvent(
                state=self.state,
                session_id=self.session_id,
                tenant_id=self.tenant_id,
                sequence=sequence,
                interrupted=interrupted,
            ))
