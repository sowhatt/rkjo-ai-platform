import pytest

from rkjo_kernel.voice import AudioInput, AudioOutput, SpeechRequest, Transcript


def test_audio_input_preserves_execution_identity():
    item = AudioInput(
        data=b"audio",
        mime_type="audio/wav",
        tenant_id="tenant-a",
        mission_id="Mission-1",
        trace_id="Trace-1",
        language="fr",
    )
    assert item.tenant_id == "tenant-a"
    assert item.mission_id == "Mission-1"
    assert item.trace_id == "Trace-1"


def test_audio_contracts_reject_empty_or_non_audio_payloads():
    with pytest.raises(ValueError):
        AudioInput(data=b"", mime_type="audio/wav", tenant_id="tenant-a")
    with pytest.raises(ValueError):
        AudioInput(data=b"x", mime_type="video/mp4", tenant_id="tenant-a")
    with pytest.raises(ValueError):
        AudioOutput(data=b"x", mime_type="text/plain", tenant_id="tenant-a")


def test_transcript_validates_confidence():
    transcript = Transcript(
        text="Bonjour RKJO",
        tenant_id="tenant-a",
        confidence=0.95,
    )
    assert transcript.confidence == 0.95
    with pytest.raises(ValueError):
        Transcript(text="x", tenant_id="tenant-a", confidence=1.01)


def test_speech_request_requires_text_and_tenant():
    with pytest.raises(ValueError):
        SpeechRequest(text="", tenant_id="tenant-a")
    with pytest.raises(ValueError):
        SpeechRequest(text="Bonjour", tenant_id=" ")
