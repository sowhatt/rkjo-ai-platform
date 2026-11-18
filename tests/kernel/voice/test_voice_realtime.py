import pytest

from rkjo_kernel.voice.realtime import (
    RealtimeVoiceController,
    RealtimeVoiceState,
    VoiceActivity,
)
from rkjo_kernel.voice.streaming import AudioChunk


class VAD:
    def __init__(self, activities):
        self.activities = iter(activities)
    def detect(self, chunk):
        return next(self.activities)


class Sink:
    def __init__(self):
        self.events = []
    def publish(self, event):
        self.events.append(event)


def chunk(sequence=0, tenant="tenant-a", session="session-1"):
    return AudioChunk(
        data=b"x",
        sequence=sequence,
        mime_type="audio/pcm",
        tenant_id=tenant,
        session_id=session,
    )


def test_vad_moves_user_speech_to_thinking():
    controller = RealtimeVoiceController(
        session_id="session-1",
        tenant_id="tenant-a",
        vad=VAD([VoiceActivity.SPEECH_STARTED, VoiceActivity.SPEECH_ENDED]),
    )
    controller.accept(chunk(0))
    assert controller.state is RealtimeVoiceState.USER_SPEAKING
    controller.accept(chunk(1))
    assert controller.state is RealtimeVoiceState.THINKING


def test_agent_speaking_cycle_returns_to_listening():
    controller = RealtimeVoiceController(
        session_id="session-1", tenant_id="tenant-a", vad=VAD([])
    )
    controller.agent_started_speaking()
    assert controller.state is RealtimeVoiceState.AGENT_SPEAKING
    controller.agent_finished_speaking()
    assert controller.state is RealtimeVoiceState.LISTENING


def test_barge_in_interrupts_agent_and_returns_ownership_to_user():
    sink = Sink()
    controller = RealtimeVoiceController(
        session_id="session-1",
        tenant_id="tenant-a",
        vad=VAD([VoiceActivity.SPEECH_STARTED]),
        sink=sink,
    )
    controller.agent_started_speaking()
    controller.accept(chunk(0))
    assert controller.state is RealtimeVoiceState.USER_SPEAKING
    assert any(
        event.state is RealtimeVoiceState.INTERRUPTED and event.interrupted
        for event in sink.events
    )


def test_realtime_controller_rejects_cross_tenant_audio():
    controller = RealtimeVoiceController(
        session_id="session-1",
        tenant_id="tenant-a",
        vad=VAD([VoiceActivity.SPEECH_STARTED]),
    )
    with pytest.raises(ValueError, match="tenant_id"):
        controller.accept(chunk(tenant="tenant-b"))


def test_closed_realtime_session_rejects_audio():
    controller = RealtimeVoiceController(
        session_id="session-1", tenant_id="tenant-a", vad=VAD([])
    )
    controller.close()
    with pytest.raises(RuntimeError, match="closed"):
        controller.accept(chunk())
