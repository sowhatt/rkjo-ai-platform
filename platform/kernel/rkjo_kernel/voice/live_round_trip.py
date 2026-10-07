"""Explicit opt-in live OpenAI voice round-trip."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rkjo_kernel.voice.live_smoke import mime_for_audio, validate_audio_file
from rkjo_kernel.voice.models import AudioInput, SpeechRequest
from rkjo_kernel.voice.openai_provider import OpenAISTTClient, OpenAITTSClient
from rkjo_kernel.voice.providers import ProviderSpeechToText, ProviderTextToSpeech


def run_round_trip(
    input_path: Path,
    output_path: Path,
    *,
    client: Any,
    language: str | None = None,
) -> str:
    data = validate_audio_file(input_path)
    stt = ProviderSpeechToText(OpenAISTTClient(client), provider="openai")
    tts = ProviderTextToSpeech(OpenAITTSClient(client), provider="openai")

    transcript = stt.transcribe(AudioInput(
        data=data,
        mime_type=mime_for_audio(input_path),
        tenant_id="rkjo-live-smoke",
        mission_id="voice-live-smoke",
        trace_id="voice-live-smoke",
        language=language,
    ))
    audio = tts.synthesize(SpeechRequest(
        text=transcript.text,
        tenant_id=transcript.tenant_id,
        mission_id=transcript.mission_id,
        trace_id=transcript.trace_id,
        language=transcript.language,
    ))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(audio.data)
    return transcript.text
