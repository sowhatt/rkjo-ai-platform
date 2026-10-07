from types import SimpleNamespace

import pytest

from rkjo_kernel.voice.openai_provider import OpenAISTTClient, OpenAITTSClient
from rkjo_kernel.voice.providers import ProviderSpeechToText, ProviderTextToSpeech
from rkjo_kernel.voice.models import AudioInput, SpeechRequest


class Transcriptions:
    def __init__(self):
        self.kwargs = None
    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(text="bonjour rkjo", language="fr")


class Speech:
    def __init__(self):
        self.kwargs = None
    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(content=b"real-provider-audio")


class Client:
    def __init__(self):
        self.audio = SimpleNamespace(
            transcriptions=Transcriptions(),
            speech=Speech(),
        )


def test_openai_stt_integrates_with_provider_adapter():
    client = Client()
    adapter = ProviderSpeechToText(
        OpenAISTTClient(client), provider="openai"
    )
    result = adapter.transcribe(AudioInput(
        data=b"wav-data", mime_type="audio/wav", tenant_id="tenant-a",
        mission_id="mission-1", trace_id="trace-1", language="fr",
    ))
    assert result.text == "bonjour rkjo"
    assert result.tenant_id == "tenant-a"
    assert result.metadata["provider"] == "openai"
    assert client.audio.transcriptions.kwargs["model"] == "gpt-4o-mini-transcribe"
    assert client.audio.transcriptions.kwargs["file"].name == "audio.wav"


def test_openai_tts_integrates_with_provider_adapter():
    client = Client()
    adapter = ProviderTextToSpeech(
        OpenAITTSClient(client), provider="openai"
    )
    result = adapter.synthesize(SpeechRequest(
        text="bonjour", tenant_id="tenant-a", mission_id="mission-1",
        trace_id="trace-1", voice="alloy", language="fr",
    ))
    assert result.data == b"real-provider-audio"
    assert result.mime_type == "audio/mpeg"
    assert result.tenant_id == "tenant-a"
    assert client.audio.speech.kwargs["model"] == "gpt-4o-mini-tts"


def test_openai_clients_fail_closed_on_empty_provider_output():
    client = Client()
    client.audio.transcriptions.create = lambda **kwargs: SimpleNamespace(text="")
    with pytest.raises(ValueError):
        OpenAISTTClient(client).transcribe(
            data=b"x", mime_type="audio/wav", language=None
        )

    client = Client()
    client.audio.speech.create = lambda **kwargs: SimpleNamespace(content=b"")
    with pytest.raises(ValueError):
        OpenAITTSClient(client).synthesize(
            text="hello", voice=None, language=None
        )
