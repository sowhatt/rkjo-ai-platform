"""Opt-in live voice smoke-test helpers."""

from __future__ import annotations

from pathlib import Path


def mime_for_audio(path: Path) -> str:
    return {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".mp4": "audio/mp4",
        ".webm": "audio/webm",
        ".ogg": "audio/ogg",
    }.get(path.suffix.lower(), "audio/wav")


def validate_audio_file(path: Path) -> bytes:
    data = path.read_bytes()
    if not data:
        raise ValueError("Input audio file is empty.")
    return data
