from rkjo_kernel.voice.models import AudioOutput, Transcript
from rkjo_kernel.voice.runtime import VoiceTurnResult
from rkjo_kernel.voice.streaming_playback import StreamingAudioPlayback


class Sink:
    def __init__(self):
        self.chunks = []
        self.interruptions = []

    def send(self, chunk):
        self.chunks.append(chunk)

    def interrupt(self, *, session_id, tenant_id):
        self.interruptions.append((session_id, tenant_id))


def turn(data=b"abcdefghij"):
    return VoiceTurnResult(
        transcript=Transcript(
            text="bonjour", tenant_id="tenant-a",
            mission_id="mission-1", trace_id="trace-1",
        ),
        response_text="salut",
        audio=AudioOutput(
            data=data, mime_type="audio/mpeg", tenant_id="tenant-a",
            mission_id="mission-1", trace_id="trace-1",
            metadata={"voice_session_id": "session-1"},
        ),
    )


def test_streaming_playback_emits_ordered_final_chunk():
    sink = Sink()
    playback = StreamingAudioPlayback(sink=sink, chunk_size=4)
    playback.play(turn())

    assert [c.data for c in sink.chunks] == [b"abcd", b"efgh", b"ij"]
    assert [c.sequence for c in sink.chunks] == [0, 1, 2]
    assert [c.is_final for c in sink.chunks] == [False, False, True]
    assert all(c.session_id == "session-1" for c in sink.chunks)
    assert all(c.mission_id == "mission-1" for c in sink.chunks)
    assert all(c.trace_id == "trace-1" for c in sink.chunks)


def test_streaming_playback_propagates_interrupt():
    sink = Sink()
    playback = StreamingAudioPlayback(sink=sink)
    playback.interrupt(session_id="session-1", tenant_id="tenant-a")
    assert sink.interruptions == [("session-1", "tenant-a")]


def test_streaming_playback_requires_session_metadata():
    sink = Sink()
    value = turn()
    bad = VoiceTurnResult(
        transcript=value.transcript,
        response_text=value.response_text,
        audio=AudioOutput(
            data=b"x", mime_type="audio/mpeg", tenant_id="tenant-a"
        ),
    )
    import pytest
    with pytest.raises(ValueError):
        StreamingAudioPlayback(sink=sink).play(bad)
