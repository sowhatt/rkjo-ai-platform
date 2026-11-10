"""OpenAI audio clients for RKJO provider-neutral voice adapters."""

from __future__ import annotations

import io
from typing import Any


class OpenAISTTClient:
    """Thin OpenAI transcription client compatible with STTClientPort."""

    def __init__(self, client: Any, *, model: str = "gpt-4o-mini-transcribe") -> None:
        if not model.strip():
            raise ValueError("OpenAI STT model cannot be empty.")
        self.client = client
        self.model = model

    def transcribe(
        self, *, data: bytes, mime_type: str, language: str | None
    ) -> tuple[str, str | None, float | None]:
        extension = _extension_for_mime(mime_type)
        audio = io.BytesIO(data)
        audio.name = f"audio.{extension}"

        kwargs: dict[str, Any] = {
            "model": self.model,
            "file": audio,
        }
        if language:
            kwargs["language"] = language

        response = self.client.audio.transcriptions.create(**kwargs)
        text = _read_value(response, "text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("OpenAI transcription returned empty text.")

        detected_language = _read_value(response, "language")
        return text, detected_language if isinstance(detected_language, str) else language, None


class OpenAITTSClient:
    """Thin OpenAI speech client compatible with TTSClientPort."""

    def __init__(
        self,
        client: Any,
        *,
        model: str = "gpt-4o-mini-tts",
        default_voice: str = "alloy",
        response_format: str = "mp3",
    ) -> None:
        if not model.strip() or not default_voice.strip():
            raise ValueError("OpenAI TTS model and voice cannot be empty.")
        self.client = client
        self.model = model
        self.default_voice = default_voice
        self.response_format = response_format

    def synthesize(
        self, *, text: str, voice: str | None, language: str | None
    ) -> tuple[bytes, str]:
        response = self.client.audio.speech.create(
            model=self.model,
            voice=voice or self.default_voice,
            input=text,
            response_format=self.response_format,
        )
        data = _audio_bytes(response)
        if not data:
            raise ValueError("OpenAI speech returned empty audio.")
        return data, _mime_for_format(self.response_format)


def _read_value(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _audio_bytes(response: Any) -> bytes:
    content = getattr(response, "content", None)
    if isinstance(content, bytes):
        return content
    read = getattr(response, "read", None)
    if callable(read):
        value = read()
        if isinstance(value, bytes):
            return value
    if isinstance(response, bytes):
        return response
    raise TypeError("Unsupported OpenAI speech response type.")


def _extension_for_mime(mime_type: str) -> str:
    return {
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/mp4": "mp4",
        "audio/webm": "webm",
        "audio/ogg": "ogg",
    }.get(mime_type.lower(), "wav")


def _mime_for_format(response_format: str) -> str:
    return {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "opus": "audio/ogg",
        "aac": "audio/aac",
        "flac": "audio/flac",
        "pcm": "audio/pcm",
    }.get(response_format.lower(), f"audio/{response_format.lower()}")
