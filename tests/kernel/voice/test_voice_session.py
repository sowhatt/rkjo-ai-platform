import pytest

from rkjo_kernel.voice import AudioInput, AudioOutput, Transcript
from rkjo_kernel.voice.runtime import VoiceRuntime
from rkjo_kernel.voice.session import (
    VoiceSession,
    VoiceSessionEngine,
    VoiceSessionState,
)


class STT:
    def transcribe(self, audio):
        return Transcript(
            text="Bonjour",
            tenant_id=audio.tenant_id,
            mission_id=audio.mission_id,
            trace_id=audio.trace_id,
        )


class Agent:
    def respond(self, transcript):
        return "Bonjour à vous."


class TTS:
    def synthesize(self, request):
        return AudioOutput(
            data=b"reply",
            mime_type="audio/wav",
            tenant_id=request.tenant_id,
            mission_id=request.mission_id,
            trace_id=request.trace_id,
        )


def engine():
    return VoiceSessionEngine(
        runtime=VoiceRuntime(
            speech_to_text=STT(),
            agent=Agent(),
            text_to_speech=TTS(),
        )
    )


def source(tenant="tenant-a"):
    return AudioInput(
        data=b"voice",
        mime_type="audio/wav",
        tenant_id=tenant,
        mission_id="Mission-1",
        trace_id="Trace-1",
    )


def session():
    return VoiceSession(
        session_id="session-1",
        tenant_id="tenant-a",
        mission_id="Mission-1",
        trace_id="Trace-1",
    )


def test_session_completes_turn_and_returns_to_listening():
    updated, result = engine().execute_turn(session(), source())
    assert updated.state is VoiceSessionState.LISTENING
    assert updated.turn_count == 1
    assert result.response_text == "Bonjour à vous."


def test_session_supports_multiple_turns():
    current = session()
    current, _ = engine().execute_turn(current, source())
    current, _ = engine().execute_turn(current, source())
    assert current.turn_count == 2
    assert current.state is VoiceSessionState.LISTENING


def test_session_rejects_cross_tenant_audio_before_runtime():
    with pytest.raises(ValueError, match="tenant_id"):
        engine().execute_turn(session(), source(tenant="tenant-b"))


def test_closed_session_rejects_new_audio():
    closed = engine().close(session())
    assert closed.state is VoiceSessionState.CLOSED
    with pytest.raises(RuntimeError, match="LISTENING"):
        engine().execute_turn(closed, source())


def test_error_state_is_explicit_and_retains_reason():
    failed = engine().mark_error(session(), RuntimeError("provider down"))
    assert failed.state is VoiceSessionState.ERROR
    assert failed.last_error == "provider down"
    assert failed.turn_count == 0
