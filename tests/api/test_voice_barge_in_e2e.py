import asyncio
import base64

from rkjo_api.voice_streaming import AsyncWebSocketAudioSink
from rkjo_kernel.voice.models import AudioOutput, Transcript
from rkjo_kernel.voice.orchestrator import RealtimeVoiceOrchestrator
from rkjo_kernel.voice.realtime import RealtimeVoiceController, VoiceActivity, RealtimeVoiceState
from rkjo_kernel.voice.runtime import VoiceRuntime
from rkjo_kernel.voice.session import VoiceSession
from rkjo_kernel.voice.streaming import AudioChunk
from rkjo_kernel.voice.streaming_playback import StreamingAudioPlayback


class VAD:
    def __init__(self):
        self.values = iter([
            VoiceActivity.SPEECH_STARTED,
            VoiceActivity.SPEECH_ENDED,
            VoiceActivity.SPEECH_STARTED,
        ])

    def detect(self, chunk):
        return next(self.values)


class STT:
    def transcribe(self, audio):
        return Transcript(
            text="bonjour",
            tenant_id=audio.tenant_id,
            mission_id=audio.mission_id,
            trace_id=audio.trace_id,
        )


class Agent:
    def respond(self, transcript):
        return "réponse"


class TTS:
    def synthesize(self, request):
        return AudioOutput(
            data=b"abcdefghij",
            mime_type="audio/mpeg",
            tenant_id=request.tenant_id,
            mission_id=request.mission_id,
            trace_id=request.trace_id,
        )


def chunk(sequence):
    return AudioChunk(
        data=b"pcm",
        sequence=sequence,
        mime_type="audio/pcm",
        tenant_id="tenant-a",
        session_id="session-1",
        mission_id="mission-1",
        trace_id="trace-1",
    )


def test_barge_in_interrupts_streaming_playback():
    async def scenario():
        sent = []

        async def send_json(payload):
            sent.append(dict(payload))

        sink = AsyncWebSocketAudioSink(send_json=send_json)
        await sink.start()

        session = VoiceSession(
            session_id="session-1",
            tenant_id="tenant-a",
            mission_id="mission-1",
            trace_id="trace-1",
        )
        controller = RealtimeVoiceController(
            session_id=session.session_id,
            tenant_id=session.tenant_id,
            vad=VAD(),
        )
        runtime = VoiceRuntime(
            speech_to_text=STT(),
            agent=Agent(),
            text_to_speech=TTS(),
        )
        playback = StreamingAudioPlayback(sink=sink, chunk_size=3)
        orchestrator = RealtimeVoiceOrchestrator(
            session=session,
            controller=controller,
            runtime=runtime,
            playback=playback,
        )

        assert orchestrator.accept(chunk(0)) is None
        result = orchestrator.accept(chunk(1))
        assert result is not None
        assert controller.state is RealtimeVoiceState.AGENT_SPEAKING

        assert orchestrator.accept(chunk(0)) is None
        await sink.drain()
        await sink.close()

        types = [p["type"] for p in sent]
        assert types[-1] == "audio.interrupted"
        assert types.count("audio.interrupted") == 1
        assert sent[-1]["session_id"] == "session-1"
        assert sent[-1]["tenant_id"] == "tenant-a"
        assert controller.state is RealtimeVoiceState.USER_SPEAKING

    asyncio.run(scenario())
