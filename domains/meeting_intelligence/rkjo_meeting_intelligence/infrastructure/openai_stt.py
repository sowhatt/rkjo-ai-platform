"""OpenAI speech-to-text adapter for Meeting Intelligence."""

from __future__ import annotations

import io
import os

from openai import OpenAI

from rkjo_meeting_intelligence.application.transcription import STTSegment


class OpenAIWhisperSTTProvider:
    """Timestamped file transcription adapter using OpenAI Whisper."""

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
        self.model = (model or os.getenv("RKJO_MEETING_STT_MODEL", "whisper-1")).strip()

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
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

        segments = getattr(result, "segments", None) or []
        return [
            STTSegment(
                text=str(segment.text).strip(),
                start_seconds=float(segment.start),
                end_seconds=float(segment.end),
            )
            for segment in segments
            if str(segment.text).strip()
        ]
