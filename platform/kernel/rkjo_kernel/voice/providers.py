"""Provider adapters for RKJO Voice.

Adapters depend only on small injected client protocols so the kernel remains
provider-neutral and tests require no network or provider SDK.
"""

from __future__ import annotations

from typing import Protocol

from rkjo_kernel.voice.models import AudioInput, AudioOutput, SpeechRequest, Transcript


class STTClientPort(Protocol):
    def transcribe(
        self, *, data: bytes, mime_type: str, language: str | None
    ) -> tuple[str, str | None, float | None]: ...


class TTSClientPort(Protocol):
    def synthesize(
        self, *, text: str, voice: str | None, language: str | None
    ) -> tuple[bytes, str]: ...


class ProviderSpeechToText:
    def __init__(self, client: STTClientPort, *, provider: str) -> None:
        if not provider.strip():
            raise ValueError("STT provider name cannot be empty.")
        self.client = client
        self.provider = provider

    def transcribe(self, audio: AudioInput) -> Transcript:
        text, language, confidence = self.client.transcribe(
            data=audio.data,
            mime_type=audio.mime_type,
            language=audio.language,
        )
        return Transcript(
            text=text,
            tenant_id=audio.tenant_id,
            mission_id=audio.mission_id,
            trace_id=audio.trace_id,
            language=language or audio.language,
            confidence=confidence,
            metadata={"provider": self.provider},
        )


class ProviderTextToSpeech:
    def __init__(self, client: TTSClientPort, *, provider: str) -> None:
        if not provider.strip():
            raise ValueError("TTS provider name cannot be empty.")
        self.client = client
        self.provider = provider

    def synthesize(self, request: SpeechRequest) -> AudioOutput:
        data, mime_type = self.client.synthesize(
            text=request.text,
            voice=request.voice,
            language=request.language,
        )
        return AudioOutput(
            data=data,
            mime_type=mime_type,
            tenant_id=request.tenant_id,
            mission_id=request.mission_id,
            trace_id=request.trace_id,
            metadata={"provider": self.provider},
        )
