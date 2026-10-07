import asyncio
import base64

from rkjo_api.voice import VoiceWebSocketGateway
from rkjo_api.voice_bridge import VoiceLiveBridge
from rkjo_api.voice_streaming import AsyncWebSocketAudioSink
from rkjo_kernel.voice.live import LiveVoiceSession
from rkjo_kernel.voice.models import AudioOutput, Transcript
from rkjo_kernel.voice.orchestrator import RealtimeVoiceOrchestrator
from rkjo_kernel.voice.realtime import RealtimeVoiceController, VoiceActivity
from rkjo_kernel.voice.runtime import VoiceRuntime
from rkjo_kernel.voice.session import VoiceSession
from rkjo_kernel.voice.streaming_playback import StreamingAudioPlayback


class Socket:
    def __init__(self, messages):
        self.messages = iter(messages); self.sent=[]; self.closed=[]
    async def accept(self): pass
    async def receive_json(self):
        try: return next(self.messages)
        except StopIteration: raise StopAsyncIteration
    async def send_json(self, payload): self.sent.append(dict(payload))
    async def close(self, code=1000): self.closed.append(code)


class Transport:
    def send(self, event): pass
    def close(self, *, session_id, tenant_id): pass


class VAD:
    def __init__(self): self.values=iter([VoiceActivity.SPEECH_STARTED, VoiceActivity.SPEECH_ENDED])
    def detect(self, chunk): return next(self.values)


class STT:
    def transcribe(self, audio):
        return Transcript(text="bonjour", tenant_id=audio.tenant_id, mission_id=audio.mission_id, trace_id=audio.trace_id)


class Agent:
    def respond(self, transcript): return "réponse rkjo"


class TTS:
    def synthesize(self, request):
        return AudioOutput(data=b"abcdefghijkl", mime_type="audio/mpeg", tenant_id=request.tenant_id, mission_id=request.mission_id, trace_id=request.trace_id)


def wire(seq):
    return {"type":"audio.chunk","data":base64.b64encode(b"pcm").decode(),"sequence":seq,"mime_type":"audio/pcm","tenant_id":"tenant-a","session_id":"session-1","mission_id":"mission-1","trace_id":"trace-1"}


def test_realtime_websocket_streaming_e2e():
    async def scenario():
        socket=Socket([wire(0), wire(1)])
        sink=AsyncWebSocketAudioSink(send_json=socket.send_json)
        await sink.start()
        session=VoiceSession(session_id="session-1",tenant_id="tenant-a",mission_id="mission-1",trace_id="trace-1")
        controller=RealtimeVoiceController(session_id=session.session_id,tenant_id=session.tenant_id,vad=VAD())
        runtime=VoiceRuntime(speech_to_text=STT(),agent=Agent(),text_to_speech=TTS())
        playback=StreamingAudioPlayback(sink=sink,chunk_size=5)
        orchestrator=RealtimeVoiceOrchestrator(session=session,controller=controller,runtime=runtime,playback=playback)
        live=LiveVoiceSession(session_id=session.session_id,tenant_id=session.tenant_id,mission_id=session.mission_id,trace_id=session.trace_id,transport=Transport())
        bridge=VoiceLiveBridge(live=live,orchestrator=orchestrator)
        gateway=VoiceWebSocketGateway(websocket=socket,tenant_id=session.tenant_id,session_id=session.session_id,mission_id=session.mission_id,trace_id=session.trace_id,on_audio=bridge.on_audio)

        await gateway.run()
        await sink.drain()
        await sink.close()

        chunks=[p for p in socket.sent if p["type"]=="audio.chunk"]
        assert [p["sequence"] for p in chunks] == [0,1,2]
        assert [base64.b64decode(p["data"]) for p in chunks] == [b"abcde",b"fghij",b"kl"]
        assert chunks[-1]["is_final"] is True
        assert all(p["session_id"]=="session-1" for p in chunks)
        assert all(p["mission_id"]=="mission-1" for p in chunks)
        assert all(p["trace_id"]=="trace-1" for p in chunks)
        assert socket.closed == [1000]

    asyncio.run(scenario())
