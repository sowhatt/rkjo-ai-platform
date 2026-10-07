import pytest

from rkjo_kernel.voice.models import AudioInput, SpeechRequest
from rkjo_kernel.voice.providers import ProviderSpeechToText, ProviderTextToSpeech


class STTClient:
    def transcribe(self, *, data, mime_type, language):
        assert data == b"voice"
        assert mime_type == "audio/wav"
        return "bonjour rkjo", "fr", 0.98


class TTSClient:
    def synthesize(self, *, text, voice, language):
        assert text == "bonjour"
        assert voice == "nova"
        return b"speech", "audio/mpeg"


def test_stt_adapter_preserves_canonical_identity():
    adapter = ProviderSpeechToText(STTClient(), provider="test-stt")
    result = adapter.transcribe(AudioInput(
        data=b"voice", mime_type="audio/wav", tenant_id="tenant-a",
        mission_id="mission-1", trace_id="trace-1", language="fr",
    ))
    assert result.text == "bonjour rkjo"
    assert result.tenant_id == "tenant-a"
    assert result.mission_id == "mission-1"
    assert result.trace_id == "trace-1"
    assert result.confidence == 0.98
    assert result.metadata["provider"] == "test-stt"


def test_tts_adapter_preserves_canonical_identity():
    adapter = ProviderTextToSpeech(TTSClient(), provider="test-tts")
    result = adapter.synthesize(SpeechRequest(
        text="bonjour", tenant_id="tenant-a", mission_id="mission-1",
        trace_id="trace-1", voice="nova", language="fr",
    ))
    assert result.data == b"speech"
    assert result.mime_type == "audio/mpeg"
    assert result.tenant_id == "tenant-a"
    assert result.mission_id == "mission-1"
    assert result.trace_id == "trace-1"
    assert result.metadata["provider"] == "test-tts"


def test_provider_names_fail_closed():
    with pytest.raises(ValueError):
        ProviderSpeechToText(STTClient(), provider=" ")
    with pytest.raises(ValueError):
        ProviderTextToSpeech(TTSClient(), provider="")
