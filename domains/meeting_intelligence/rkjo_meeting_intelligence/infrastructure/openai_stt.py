"""OpenAI speech-to-text adapter for Meeting Intelligence."""

from __future__ import annotations

import io
import os

from openai import OpenAI

from rkjo_meeting_intelligence.application.transcription import STTSegment


class OpenAIGPTTranscribeProvider:
    """High-accuracy file transcription adapter using GPT-Transcribe."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        resolved_key = (api_key or os.getenv("OPENAI_API_KEY", "")).strip()
        if not resolved_key:
            raise RuntimeError("OPENAI_API_KEY is required for transcription.")
        self.client = OpenAI(api_key=resolved_key)
        self.model = (model or os.getenv("RKJO_MEETING_STT_MODEL", "gpt-transcribe")).strip()

    def transcribe(
        self,
        *,
        content: bytes,
        filename: str,
        content_type: str,
    ) -> list[STTSegment]:
        if not content:
            raise ValueError("audio content must not be empty.")

        media = io.BytesIO(content)
        media.name = filename
        result = self.client.audio.transcriptions.create(
            model=self.model,
            file=media,
            response_format="json",
        )

        text = str(getattr(result, "text", "")).strip()
        if not text:
            return []

        return [
            STTSegment(
                text=text,
                start_seconds=0.0,
                end_seconds=0.0,
            )
        ]
