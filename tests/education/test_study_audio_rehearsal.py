"""Synthetic audio + genuine PostgreSQL workflow/outbox, no broker or ASR.

Run with RKJO_EDUCATION_AUDIO_TEST_DATABASE_URL pointing to a disposable DB.
"""
import os
from uuid import uuid4

import psycopg
import pytest

from rkjo_education.curriculum.study_audio_probe import probe_study_wav
from rkjo_education.curriculum.study_audio_postgres import PostgresStudyAudioStaging
from rkjo_education.curriculum.study_audio_rehearsal import (
    REHEARSAL_QUEUE, SyntheticAudioRehearsal,
)
from rkjo_education.curriculum.study_audio_synthetic import make_synthetic_study_wav
from rkjo_kernel.workflow.async_dispatch import AsyncWorkflowDispatcher

TEST_URL = os.getenv("RKJO_EDUCATION_AUDIO_TEST_DATABASE_URL")


class DisabledBus:
    def publish_agent_message(self, *, queue_name, message):
        raise AssertionError("Synthetic rehearsal must never publish")


def test_synthetic_wav_duration_and_content():
    wav = make_synthetic_study_wav(seconds=3)
    probe = probe_study_wav(wav)
    assert probe.duration_ms == 3000
    assert probe.channels == 1
    assert make_synthetic_study_wav(seconds=3) == wav


def test_bad_fixture_duration():
    with pytest.raises(ValueError):
        make_synthetic_study_wav(seconds=0)


@pytest.mark.skipif(not TEST_URL, reason="Dedicated disposable PostgreSQL test URL required")
def test_durable_rehearsal_is_idempotent_isolated_and_never_published():
    tenant = "synthetic-" + str(uuid4())
    learner = "student-1"
    staging = PostgresStudyAudioStaging(TEST_URL)
    rehearsal = SyntheticAudioRehearsal(TEST_URL)
    staging.initialize_schema()
    rehearsal.initialize_schema()
    wav = make_synthetic_study_wav(seconds=1)
    probe = probe_study_wav(wav)
    try:
        source = staging.stage(
            tenant_id=tenant, learner_id=learner,
            programme_id="medicine", ue_id="cardiology",
            filename="rkjo-synthetic-lecture.wav",
            data=wav, probe=probe,
        )
        dispatcher = AsyncWorkflowDispatcher(event_bus=DisabledBus())
        with pytest.raises(LookupError):
            rehearsal.enqueue(
                tenant_id="other-tenant", learner_id=learner,
                source_id=source["source_id"], dispatcher=dispatcher,
            )
        first = rehearsal.enqueue(
            tenant_id=tenant, learner_id=learner,
            source_id=source["source_id"], dispatcher=dispatcher,
        )
        second = rehearsal.enqueue(
            tenant_id=tenant, learner_id=learner,
            source_id=source["source_id"], dispatcher=dispatcher,
        )
        assert first.created is True
        assert second.created is False
        assert second.execution_id == first.execution_id
        with psycopg.connect(TEST_URL) as conn:
            row = conn.execute("""
                SELECT status FROM workflow_executions WHERE execution_id=%s
            """, (first.execution_id,)).fetchone()
            assert row == ("running",)
            outbox_rows = conn.execute("""
                SELECT queue_name, published_at
                FROM workflow_outbox WHERE outbox_id=%s
            """, (first.outbox_id,)).fetchall()
            assert outbox_rows == [(REHEARSAL_QUEUE, None)]
    finally:
        with psycopg.connect(TEST_URL) as conn:
            # Delete only identifiers produced in this run, never other rows.
            if "first" in locals():
                conn.execute("DELETE FROM workflow_outbox WHERE outbox_id=%s", (first.outbox_id,))
                conn.execute("DELETE FROM workflow_executions WHERE execution_id=%s", (first.execution_id,))
            conn.execute("DELETE FROM education_staged_audio WHERE tenant_id=%s", (tenant,))
