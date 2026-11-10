import pytest

from rkjo_kernel.voice.live import LiveVoiceEventType, LiveVoiceSession
from rkjo_kernel.voice.models import AudioOutput, Transcript
from rkjo_kernel.voice.streaming import AudioChunk


class Transport:
    def __init__(self):
        self.events = []
        self.closed = []
    def send(self, event):
        self.events.append(event)
    def close(self, *, session_id, tenant_id):
        self.closed.append((session_id, tenant_id))


def live():
    transport = Transport()
    session = LiveVoiceSession(
        session_id="session-1",
        tenant_id="tenant-a",
        mission_id="mission-1",
        trace_id="trace-1",
        transport=transport,
    )
    return session, transport


def test_live_session_emits_ordered_lifecycle_events():
    session, transport = live()
    chunk = AudioChunk(
        data=b"x", sequence=0, mime_type="audio/pcm",
        tenant_id="tenant-a", session_id="session-1",
        mission_id="mission-1", trace_id="trace-1",
    )
    transcript = Transcript(
        text="bonjour", tenant_id="tenant-a",
        mission_id="mission-1", trace_id="trace-1",
    )
    audio = AudioOutput(
        data=b"reply", mime_type="audio/pcm", tenant_id="tenant-a",
        mission_id="mission-1", trace_id="trace-1",
    )
    session.audio_received(chunk)
    session.transcript_ready(transcript)
    session.thinking()
    session.audio_ready(audio)
    session.close()
    assert [e.event_type for e in transport.events] == [
        LiveVoiceEventType.SESSION_OPENED,
        LiveVoiceEventType.AUDIO_IN,
        LiveVoiceEventType.TRANSCRIPT,
        LiveVoiceEventType.THINKING,
        LiveVoiceEventType.AUDIO_OUT,
        LiveVoiceEventType.SESSION_CLOSED,
    ]
    assert transport.closed == [("session-1", "tenant-a")]


def test_live_session_rejects_cross_tenant_chunk():
    session, _ = live()
    chunk = AudioChunk(
        data=b"x", sequence=0, mime_type="audio/pcm",
        tenant_id="tenant-b", session_id="session-1",
        mission_id="mission-1", trace_id="trace-1",
    )
    with pytest.raises(ValueError, match="tenant_id"):
        session.audio_received(chunk)


def test_live_session_rejects_wrong_trace_transcript():
    session, _ = live()
    transcript = Transcript(
        text="bonjour", tenant_id="tenant-a",
        mission_id="mission-1", trace_id="wrong",
    )
    with pytest.raises(ValueError, match="trace_id"):
        session.transcript_ready(transcript)


def test_closed_live_session_rejects_new_events():
    session, _ = live()
    session.close()
    with pytest.raises(RuntimeError, match="closed"):
        session.thinking()


def test_live_session_emits_interruption_and_error():
    session, transport = live()
    session.interrupted(sequence=4)
    session.error("provider unavailable")
    assert transport.events[-2].event_type is LiveVoiceEventType.INTERRUPTED
    assert transport.events[-2].sequence == 4
    assert transport.events[-1].event_type is LiveVoiceEventType.ERROR
    assert transport.events[-1].error == "provider unavailable"
