import io
import wave

import pytest

from rkjo_education.curriculum.study_audio_probe import StudyAudioError, probe_study_wav


def wav_bytes(seconds=2, rate=8000):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(b"\x00\x00" * seconds * rate)
    return buffer.getvalue()


def test_wav_duration_is_read_from_real_audio():
    data = wav_bytes(seconds=2)
    result = probe_study_wav(data)
    assert result.duration_ms == 2000
    assert result.size_bytes == len(data)
    assert result.sample_rate == 8000
    assert len(result.sha256) == 64


def test_rejects_false_wav_header():
    with pytest.raises(StudyAudioError, match="RIFF/WAVE"):
        probe_study_wav(b"not-a-wave" * 10)


def test_rejects_truncated_wav():
    data = wav_bytes(seconds=2)
    with pytest.raises(StudyAudioError):
        probe_study_wav(data[:-100])


def test_rejects_empty_file():
    with pytest.raises(StudyAudioError, match="non-empty"):
        probe_study_wav(b"")


def test_rejects_invalid_pcm_parameters():
    with pytest.raises(StudyAudioError):
        probe_study_wav(wav_bytes(seconds=2, rate=4000))
