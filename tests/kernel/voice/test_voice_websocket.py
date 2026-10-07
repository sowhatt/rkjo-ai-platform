import base64
import pytest

from rkjo_kernel.voice.live import LiveVoiceEvent, LiveVoiceEventType
from rkjo_kernel.voice.models import AudioOutput, Transcript
from rkjo_kernel.voice.websocket import VoiceWebSocketCodec, VoiceWebSocketTransport


def test_codec_decodes_audio_chunk():
    payload = {
        "type": "audio.chunk",
        "data": base64.b64encode(b"pcm").decode("ascii"),
        "sequence": 2,
        "mime_type": "audio/pcm",
        "tenant_id": "tenant-a",
        "session_id": "session-1",
        "mission_id": "mission-1",
        "trace_id": "trace-1",
        "is_final": True,
    }
    chunk = VoiceWebSocketCodec.decode_audio(payload)
    assert chunk.data == b"pcm"
    assert chunk.sequence == 2
    assert chunk.is_final is True
    assert chunk.trace_id == "trace-1"


def test_codec_rejects_invalid_base64():
    payload = {
        "type": "audio.chunk", "data": "***", "sequence": 0,
        "mime_type": "audio/pcm", "tenant_id": "tenant-a",
        "session_id": "session-1",
    }
    with pytest.raises(ValueError, match="base64"):
        VoiceWebSocketCodec.decode_audio(payload)


def test_codec_encodes_transcript_without_exposing_identity_inside_body():
    transcript = Transcript(
        text="bonjour", tenant_id="tenant-a",
        mission_id="mission-1", trace_id="trace-1", confidence=0.9,
    )
    event = LiveVoiceEvent(
        event_type=LiveVoiceEventType.TRANSCRIPT,
        session_id="session-1", tenant_id="tenant-a",
        mission_id="mission-1", trace_id="trace-1",
        transcript=transcript,
    )
    payload = VoiceWebSocketCodec.encode_event(event)
    assert payload["type"] == "transcript"
    assert payload["transcript"]["text"] == "bonjour"
    assert "tenant_id" not in payload["transcript"]


def test_codec_encodes_audio_output_as_base64():
    audio = AudioOutput(
        data=b"reply", mime_type="audio/pcm", tenant_id="tenant-a",
        mission_id="mission-1", trace_id="trace-1",
    )
    event = LiveVoiceEvent(
        event_type=LiveVoiceEventType.AUDIO_OUT,
        session_id="session-1", tenant_id="tenant-a",
        mission_id="mission-1", trace_id="trace-1", audio=audio,
    )
    payload = VoiceWebSocketCodec.encode_event(event)
    assert base64.b64decode(payload["audio"]["data"]) == b"reply"


class Peer:
    def __init__(self):
        self.payloads = []
        self.closed = False
    def send_json(self, payload):
        self.payloads.append(payload)
    def close(self):
        self.closed = True


def test_websocket_transport_sends_and_closes():
    peer = Peer()
    transport = VoiceWebSocketTransport(peer=peer)
    event = LiveVoiceEvent(
        event_type=LiveVoiceEventType.THINKING,
        session_id="session-1", tenant_id="tenant-a",
    )
    transport.send(event)
    assert peer.payloads[-1]["type"] == "thinking"
    transport.close(session_id="session-1", tenant_id="tenant-a")
    assert peer.closed is True
    with pytest.raises(RuntimeError, match="closed"):
        transport.send(event)
