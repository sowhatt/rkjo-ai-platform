from rkjo_kernel.voice.models import AudioOutput, Transcript
from rkjo_kernel.voice.orchestrator import RealtimeVoiceOrchestrator
from rkjo_kernel.voice.realtime import RealtimeVoiceController, RealtimeVoiceState, VoiceActivity
from rkjo_kernel.voice.runtime import VoiceRuntime
from rkjo_kernel.voice.session import VoiceSession
from rkjo_kernel.voice.streaming import AudioChunk


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
        return "Bonjour, comment puis-je aider ?"


class TTS:
    def synthesize(self, request):
        return AudioOutput(
            data=b"reply",
            mime_type="audio/pcm",
            tenant_id=request.tenant_id,
            mission_id=request.mission_id,
            trace_id=request.trace_id,
        )


class VAD:
    def __init__(self, activities):
        self.activities = iter(activities)
    def detect(self, chunk):
        return next(self.activities)


class Playback:
    def __init__(self):
        self.played = []
        self.interruptions = []
    def play(self, result):
        self.played.append(result)
    def interrupt(self, *, session_id, tenant_id):
        self.interruptions.append((session_id, tenant_id))


def chunk(seq, *, final=False):
    return AudioChunk(
        data=b"x",
        sequence=seq,
        mime_type="audio/pcm",
        tenant_id="tenant-a",
        session_id="session-1",
        mission_id="mission-1",
        trace_id="trace-1",
        is_final=final,
    )


def make(activities):
    session = VoiceSession(
        session_id="session-1",
        tenant_id="tenant-a",
        mission_id="mission-1",
        trace_id="trace-1",
    )
    controller = RealtimeVoiceController(
        session_id=session.session_id,
        tenant_id=session.tenant_id,
        vad=VAD(activities),
    )
    playback = Playback()
    runtime = VoiceRuntime(speech_to_text=STT(), agent=Agent(), text_to_speech=TTS())
    return RealtimeVoiceOrchestrator(
        session=session, controller=controller, runtime=runtime, playback=playback
    ), playback


def test_realtime_orchestrator_executes_end_to_end_turn():
    orchestrator, playback = make([
        VoiceActivity.SPEECH_STARTED,
        VoiceActivity.SPEECH_ENDED,
    ])
    assert orchestrator.accept(chunk(0)) is None
    result = orchestrator.accept(chunk(1, final=True))
    assert result is not None
    assert result.turn.transcript.text == "bonjour"
    assert result.turn.response_text.startswith("Bonjour")
    assert result.turn.audio.data == b"reply"
    assert result.session.turn_count == 1
    assert len(playback.played) == 1
    assert orchestrator.controller.state is RealtimeVoiceState.AGENT_SPEAKING


def test_playback_finished_returns_controller_to_listening():
    orchestrator, _ = make([
        VoiceActivity.SPEECH_STARTED,
        VoiceActivity.SPEECH_ENDED,
    ])
    orchestrator.accept(chunk(0))
    orchestrator.accept(chunk(1, final=True))
    orchestrator.playback_finished()
    assert orchestrator.controller.state is RealtimeVoiceState.LISTENING


def test_barge_in_interrupts_playback_and_starts_new_utterance():
    orchestrator, playback = make([
        VoiceActivity.SPEECH_STARTED,
        VoiceActivity.SPEECH_ENDED,
        VoiceActivity.SPEECH_STARTED,
    ])
    orchestrator.accept(chunk(0))
    orchestrator.accept(chunk(1, final=True))
    assert orchestrator.controller.state is RealtimeVoiceState.AGENT_SPEAKING

    # Sequence restarts because barge-in starts a fresh utterance stream.
    orchestrator.accept(chunk(0))
    assert playback.interruptions == [("session-1", "tenant-a")]
    assert orchestrator.controller.state is RealtimeVoiceState.USER_SPEAKING
