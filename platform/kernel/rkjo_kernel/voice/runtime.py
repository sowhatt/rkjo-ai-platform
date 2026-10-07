"""Provider-neutral synchronous voice orchestration for RKJO."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from rkjo_kernel.voice.models import AudioInput, AudioOutput, SpeechRequest, Transcript
from rkjo_kernel.voice.ports import SpeechToTextPort, TextToSpeechPort


class VoiceAgentPort(Protocol):
    """Minimal boundary between Voice Runtime and an RKJO agent/application."""

    def respond(self, transcript: Transcript) -> str: ...


@dataclass(frozen=True, slots=True)
class VoiceTurnResult:
    transcript: Transcript
    response_text: str
    audio: AudioOutput


class VoiceRuntime:
    """Execute one speech -> agent -> speech turn.

    Realtime/session concerns deliberately stay outside this S28 foundation.
    """

    def __init__(
        self,
        *,
        speech_to_text: SpeechToTextPort,
        agent: VoiceAgentPort,
        text_to_speech: TextToSpeechPort,
    ) -> None:
        self.speech_to_text = speech_to_text
        self.agent = agent
        self.text_to_speech = text_to_speech

    def execute(self, audio: AudioInput) -> VoiceTurnResult:
        transcript = self.speech_to_text.transcribe(audio)
        self._validate_transcript_identity(audio, transcript)

        response_text = self.agent.respond(transcript)
        if not isinstance(response_text, str) or not response_text.strip():
            raise ValueError("Voice agent response cannot be empty.")

        speech_request = SpeechRequest(
            text=response_text,
            tenant_id=audio.tenant_id,
            mission_id=audio.mission_id,
            trace_id=audio.trace_id,
            language=transcript.language or audio.language,
            metadata={
                "voice_input_mime_type": audio.mime_type,
            },
        )
        output = self.text_to_speech.synthesize(speech_request)
        self._validate_output_identity(audio, output)

        return VoiceTurnResult(
            transcript=transcript,
            response_text=response_text,
            audio=output,
        )

    @staticmethod
    def _validate_transcript_identity(
        audio: AudioInput,
        transcript: Transcript,
    ) -> None:
        if transcript.tenant_id != audio.tenant_id:
            raise ValueError("STT transcript tenant_id conflicts with AudioInput.")
        if transcript.mission_id != audio.mission_id:
            raise ValueError("STT transcript mission_id conflicts with AudioInput.")
        if transcript.trace_id != audio.trace_id:
            raise ValueError("STT transcript trace_id conflicts with AudioInput.")

    @staticmethod
    def _validate_output_identity(
        audio: AudioInput,
        output: AudioOutput,
    ) -> None:
        if output.tenant_id != audio.tenant_id:
            raise ValueError("TTS audio tenant_id conflicts with AudioInput.")
        if output.mission_id != audio.mission_id:
            raise ValueError("TTS audio mission_id conflicts with AudioInput.")
        if output.trace_id != audio.trace_id:
            raise ValueError("TTS audio trace_id conflicts with AudioInput.")
