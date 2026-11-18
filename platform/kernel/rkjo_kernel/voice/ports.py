"""Ports implemented by voice providers."""

from __future__ import annotations

from typing import Protocol

from rkjo_kernel.voice.models import AudioInput, AudioOutput, SpeechRequest, Transcript


class SpeechToTextPort(Protocol):
    def transcribe(self, audio: AudioInput) -> Transcript: ...


class TextToSpeechPort(Protocol):
    def synthesize(self, request: SpeechRequest) -> AudioOutput: ...
