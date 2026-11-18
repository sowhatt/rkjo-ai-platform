import asyncio
import base64

from rkjo_api.voice import VoiceWebSocketGateway
from rkjo_api.voice_bridge import VoiceLiveBridge
from rkjo_kernel.voice.live import LiveVoiceSession
from rkjo_kernel.voice.models import AudioOutput, Transcript
from rkjo_kernel.voice.orchestrator import RealtimeVoiceOrchestrator
from rkjo_kernel.voice.realtime import RealtimeVoiceController, VoiceActivity
from rkjo_kernel.voice.runtime import VoiceRuntime
from rkjo_kernel.voice.session import VoiceSession
from rkjo_kernel.voice.websocket import VoiceWebSocketCodec


class Socket:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.accepted = False
        self.sent = []
        self.closed = []
    async def accept(self):
        self.accepted = True
    async def receive_json(self):
        try:
            return next(self.messages)
        except StopIteration:
            raise StopAsyncIteration
    async def send_json(self, payload):
        self.sent.append(dict(payload))
    async def close(self, code=1000):
        self.closed.append(code)


class AsyncTransport:
    """Test transport collecting live events before WebSocket wire encoding."""
    def __init__(self, socket):
        self.socket = socket
        self.events = []
    def send(self, event):
        self.events.append(event)
        self.socket.sent.append(VoiceWebSocketCodec.encode_event(event))
    def close(self, *, session_id, tenant_id):
        pass


class VAD:
    def __init__(self):
        self.values = iter([VoiceActivity.SPEECH_STARTED, VoiceActivity.SPEECH_ENDED])
    def detect(self, chunk):
        return next(self.values)


class STT:
    def transcribe(self, audio):
        return Transcript(
            text="bonjour rkjo", tenant_id=audio.tenant_id,
            mission_id=audio.mission_id, trace_id=audio.trace_id,
        )


class Agent:
    def respond(self, transcript):
        return "Bonjour depuis RKJO"


class TTS:
    def synthesize(self, request):
        return AudioOutput(
            data=b"rkjo-audio", mime_type="audio/pcm",
            tenant_id=request.tenant_id, mission_id=request.mission_id,
            trace_id=request.trace_id,
        )


class Playback:
    def __init__(self):
        self.played = []
    def play(self, result):
        self.played.append(result)
    def interrupt(self, *, session_id, tenant_id):
        pass


def wire(sequence, final=False):
    return {
        "type": "audio.chunk",
        "data": base64.b64encode(b"pcm").decode("ascii"),
        "sequence": sequence,
        "mime_type": "audio/pcm",
        "tenant_id": "tenant-a",
        "session_id": "session-1",
        "mission_id": "mission-1",
        "trace_id": "trace-1",
        "is_final": final,
    }


def test_websocket_to_audio_response_e2e():
    socket = Socket([wire(0), wire(1, True)])
    session = VoiceSession(
        session_id="session-1", tenant_id="tenant-a",
        mission_id="mission-1", trace_id="trace-1",
    )
    controller = RealtimeVoiceController(
        session_id=session.session_id, tenant_id=session.tenant_id, vad=VAD(),
    )
    runtime = VoiceRuntime(
        speech_to_text=STT(), agent=Agent(), text_to_speech=TTS(),
    )
    playback = Playback()
    orchestrator = RealtimeVoiceOrchestrator(
        session=session, controller=controller, runtime=runtime, playback=playback,
    )
    transport = AsyncTransport(socket)
    live = LiveVoiceSession(
        session_id=session.session_id, tenant_id=session.tenant_id,
        mission_id=session.mission_id, trace_id=session.trace_id,
        transport=transport,
    )
    bridge = VoiceLiveBridge(live=live, orchestrator=orchestrator)
    gateway = VoiceWebSocketGateway(
        websocket=socket, tenant_id=session.tenant_id,
        session_id=session.session_id, mission_id=session.mission_id,
        trace_id=session.trace_id, on_audio=bridge.on_audio,
    )

    asyncio.run(gateway.run())

    types = [payload["type"] for payload in socket.sent]
    assert "audio_in" in types
    assert "transcript" in types
    assert "thinking" in types
    assert "audio_out" in types
    outgoing = next(p for p in socket.sent if p["type"] == "audio_out")
    assert base64.b64decode(outgoing["audio"]["data"]) == b"rkjo-audio"
    assert len(playback.played) == 1
    assert socket.closed == [1000]
