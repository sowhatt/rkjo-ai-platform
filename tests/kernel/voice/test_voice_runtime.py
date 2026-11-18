import pytest

from rkjo_kernel.voice import AudioInput, AudioOutput, SpeechRequest, Transcript
from rkjo_kernel.voice.runtime import VoiceRuntime


class FakeSTT:
    def transcribe(self, audio):
        return Transcript(
            text="Quel temps fait-il ?",
            tenant_id=audio.tenant_id,
            mission_id=audio.mission_id,
            trace_id=audio.trace_id,
            language="fr",
            confidence=0.98,
        )


class FakeAgent:
    def __init__(self):
        self.transcript = None

    def respond(self, transcript):
        self.transcript = transcript
        return "Il fait beau."


class FakeTTS:
    def __init__(self):
        self.request = None

    def synthesize(self, request: SpeechRequest):
        self.request = request
        return AudioOutput(
            data=b"spoken-response",
            mime_type="audio/mpeg",
            tenant_id=request.tenant_id,
            mission_id=request.mission_id,
            trace_id=request.trace_id,
        )


def audio():
    return AudioInput(
        data=b"input-audio",
        mime_type="audio/wav",
        tenant_id="tenant-a",
        mission_id="Mission-1",
        trace_id="Trace-1",
        language="fr",
    )


def test_voice_runtime_executes_complete_turn_and_preserves_identity():
    agent = FakeAgent()
    tts = FakeTTS()
    runtime = VoiceRuntime(
        speech_to_text=FakeSTT(),
        agent=agent,
        text_to_speech=tts,
    )

    result = runtime.execute(audio())

    assert result.transcript.text == "Quel temps fait-il ?"
    assert result.response_text == "Il fait beau."
    assert result.audio.data == b"spoken-response"
    assert agent.transcript.tenant_id == "tenant-a"
    assert tts.request.tenant_id == "tenant-a"
    assert tts.request.mission_id == "Mission-1"
    assert tts.request.trace_id == "Trace-1"
    assert tts.request.language == "fr"


def test_voice_runtime_rejects_cross_tenant_stt_result():
    class WrongTenantSTT:
        def transcribe(self, source):
            return Transcript(
                text="Bonjour",
                tenant_id="tenant-b",
                mission_id=source.mission_id,
                trace_id=source.trace_id,
            )

    runtime = VoiceRuntime(
        speech_to_text=WrongTenantSTT(),
        agent=FakeAgent(),
        text_to_speech=FakeTTS(),
    )
    with pytest.raises(ValueError, match="tenant_id"):
        runtime.execute(audio())


def test_voice_runtime_rejects_cross_mission_tts_result():
    class WrongMissionTTS:
        def synthesize(self, request):
            return AudioOutput(
                data=b"x",
                mime_type="audio/wav",
                tenant_id=request.tenant_id,
                mission_id="Other-Mission",
                trace_id=request.trace_id,
            )

    runtime = VoiceRuntime(
        speech_to_text=FakeSTT(),
        agent=FakeAgent(),
        text_to_speech=WrongMissionTTS(),
    )
    with pytest.raises(ValueError, match="mission_id"):
        runtime.execute(audio())


def test_voice_runtime_rejects_empty_agent_response_before_tts():
    class EmptyAgent:
        def respond(self, transcript):
            return " "

    class MustNotRunTTS:
        def synthesize(self, request):
            raise AssertionError("TTS must not run")

    runtime = VoiceRuntime(
        speech_to_text=FakeSTT(),
        agent=EmptyAgent(),
        text_to_speech=MustNotRunTTS(),
    )
    with pytest.raises(ValueError, match="cannot be empty"):
        runtime.execute(audio())
