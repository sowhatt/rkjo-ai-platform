import pytest

from rkjo_kernel.voice import VoiceSession
from rkjo_kernel.voice.streaming import AudioChunk, VoiceStream, VoiceStreamEventType


class Sink:
    def __init__(self):
        self.events = []
    def publish(self, event):
        self.events.append(event)


def session():
    return VoiceSession(
        session_id="session-1",
        tenant_id="tenant-a",
        mission_id="Mission-1",
        trace_id="Trace-1",
    )


def chunk(sequence, data=b"x", *, tenant="tenant-a", final=False):
    return AudioChunk(
        data=data,
        sequence=sequence,
        mime_type="audio/pcm",
        tenant_id=tenant,
        session_id="session-1",
        mission_id="Mission-1",
        trace_id="Trace-1",
        is_final=final,
    )


def test_stream_reassembles_ordered_audio_and_identity():
    stream = VoiceStream(session=session())
    stream.push(chunk(0, b"hello "))
    stream.push(chunk(1, b"world", final=True))
    audio = stream.finalize()
    assert audio.data == b"hello world"
    assert audio.tenant_id == "tenant-a"
    assert audio.metadata["voice_session_id"] == "session-1"


def test_stream_rejects_out_of_order_chunks():
    stream = VoiceStream(session=session())
    with pytest.raises(ValueError, match="sequence 0"):
        stream.push(chunk(1))


def test_stream_rejects_cross_tenant_chunk():
    stream = VoiceStream(session=session())
    with pytest.raises(ValueError, match="tenant_id"):
        stream.push(chunk(0, tenant="tenant-b"))


def test_final_chunk_prevents_more_audio():
    stream = VoiceStream(session=session())
    stream.push(chunk(0, final=True))
    with pytest.raises(RuntimeError, match="finalized"):
        stream.push(chunk(1))


def test_stream_emits_lifecycle_events():
    sink = Sink()
    stream = VoiceStream(session=session(), sink=sink)
    stream.push(chunk(0, final=True))
    stream.finalize()
    stream.close()
    assert [e.event_type for e in sink.events] == [
        VoiceStreamEventType.OPENED,
        VoiceStreamEventType.AUDIO_RECEIVED,
        VoiceStreamEventType.FINALIZED,
        VoiceStreamEventType.CLOSED,
    ]
