"""Dedicated disposable PostgreSQL only; NEVER run against default RKJO database."""
import io
import os
import wave

import pytest

from rkjo_education.curriculum.study_audio_probe import probe_study_wav
from rkjo_education.curriculum.study_audio_postgres import (
    PostgresStudyAudioStaging, StagedAudioNotFound,
)

TEST_URL = os.getenv("RKJO_EDUCATION_AUDIO_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_URL, reason="Dedicated audio test database URL required")


def audio():
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 8000)
    return output.getvalue()


def test_audio_stage_is_durable_idempotent_and_tenant_safe():
    store = PostgresStudyAudioStaging(TEST_URL)
    store.initialize_schema()
    data = audio()
    probe = probe_study_wav(data)
    from uuid import uuid4
    tenant = "test-" + str(uuid4())
    learner = "student-a"
    try:
        a = store.stage(
            tenant_id=tenant, learner_id=learner, programme_id="medicine",
            ue_id="physiology", filename="lesson.wav", data=data, probe=probe,
        )
        b = store.stage(
            tenant_id=tenant, learner_id=learner, programme_id="medicine",
            ue_id="physiology", filename="lesson.wav", data=data, probe=probe,
        )
        assert a["source_id"] == b["source_id"]
        assert a["state"] == "staged"
        assert a["duration_ms"] == 1000
        assert not a["transcription_started"]
        with pytest.raises(StagedAudioNotFound):
            store.get(tenant_id="someone-else", learner_id=learner, source_id=a["source_id"])
        with pytest.raises(StagedAudioNotFound):
            store.get(tenant_id=tenant, learner_id="student-b", source_id=a["source_id"])
        assert not store.delete(tenant_id=tenant, learner_id="student-b", source_id=a["source_id"])
        assert store.delete(tenant_id=tenant, learner_id=learner, source_id=a["source_id"])
        with pytest.raises(StagedAudioNotFound):
            store.get(tenant_id=tenant, learner_id=learner, source_id=a["source_id"])
    finally:
        # Clean up only the unique tenant rows created in this test.
        import psycopg
        with psycopg.connect(TEST_URL) as connection:
            connection.execute("DELETE FROM education_staged_audio WHERE tenant_id=%s", (tenant,))
