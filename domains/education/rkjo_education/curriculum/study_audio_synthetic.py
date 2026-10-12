"""Deterministic non-speech WAV fixture for audio infrastructure tests.

Silence/tone is intentionally not presented as a lecture or ASR benchmark.
"""
from __future__ import annotations

from io import BytesIO
from math import sin, pi
import struct
import wave


def make_synthetic_study_wav(*, seconds: int = 2, sample_rate: int = 8000) -> bytes:
    if not (1 <= seconds <= 120):
        raise ValueError("Fixture duration must be between 1 and 120 seconds")
    if sample_rate not in (8000, 16000):
        raise ValueError("Only test sample rates 8000 and 16000 Hz are supported")
    # 1 kHz tone, 16-bit mono. Suitable for metadata/ingestion tests, NOT ASR.
    samples = bytearray()
    for index in range(seconds * sample_rate):
        sample = int(4000 * sin(2 * pi * 1000 * index / sample_rate))
        samples.extend(struct.pack("<h", sample))
    result = BytesIO()
    with wave.open(result, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(bytes(samples))
    return result.getvalue()
