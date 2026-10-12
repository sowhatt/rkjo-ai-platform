"""WAV-only first admission gate: no storage, transcription or side effects."""
from __future__ import annotations

import hashlib
import io
import wave
from dataclasses import dataclass

from rkjo_education.curriculum.study_media_intake import AUDIO_MAX_BYTES


class StudyAudioError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AudioProbe:
    sha256: str
    duration_ms: int
    sample_rate: int
    channels: int
    size_bytes: int
    encoding: str


def probe_study_wav(data: bytes) -> AudioProbe:
    if not data or len(data) > AUDIO_MAX_BYTES:
        raise StudyAudioError("Audio must be non-empty and <= 50 MiB")
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise StudyAudioError("First pilot only supports real RIFF/WAVE files")
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            if wav.getcomptype() != "NONE":
                raise StudyAudioError("Compressed WAV not supported")
            rate = wav.getframerate()
            frames = wav.getnframes()
            channels = wav.getnchannels()
            width = wav.getsampwidth()
            if rate < 8000 or rate > 192000 or channels not in (1, 2) or width not in (1, 2, 3, 4):
                raise StudyAudioError("Unsupported audio parameters")
            if frames <= 0:
                raise StudyAudioError("Empty audio")
            expected = frames * channels * width
            actual = len(wav.readframes(frames))
            if actual != expected:
                raise StudyAudioError("Truncated WAV audio")
            duration_ms = round(frames * 1000 / rate)
            if duration_ms <= 0 or duration_ms > 10 * 60 * 60 * 1000:
                raise StudyAudioError("Unsupported recording duration")
    except (wave.Error, EOFError, OverflowError, OSError, ValueError) as exc:
        if isinstance(exc, StudyAudioError):
            raise
        raise StudyAudioError("Invalid WAV structure") from exc
    return AudioProbe(
        sha256=hashlib.sha256(data).hexdigest(),
        duration_ms=duration_ms,
        sample_rate=rate,
        channels=channels,
        size_bytes=len(data),
        encoding="pcm-wav",
    )
