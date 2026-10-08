"""Opt-in PostgreSQL integration tests: RKJO_TEST_DATABASE_URL is required."""
from __future__ import annotations

import os
from uuid import uuid4

import psycopg
import pytest

from rkjo_kernel.multimodal.jobs import IngestionJob, JobStatus
from rkjo_kernel.multimodal.postgres_jobs import PostgreSQLIngestionJobAdapter
from rkjo_kernel.workflow.postgres_unit_of_work import PostgreSQLWorkflowUnitOfWork


@pytest.fixture
def database():
    url = os.getenv("RKJO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RKJO_TEST_DATABASE_URL for PostgreSQL job integration tests.")
    PostgreSQLWorkflowUnitOfWork(url).initialize_schema()
    adapter = PostgreSQLIngestionJobAdapter(url)
    adapter.initialize_schema()
    return url, adapter


def new_job():
    token = uuid4().hex
    return IngestionJob(
        job_id=f"job-{token}", tenant_id=f"tenant-{token}",
        idempotency_key=f"key-{token}", channel="whatsapp",
        recipient_ref="opaque", correlation_id=f"corr-{token}",
        mission_id="m1", trace_id="t1",
    )


def test_accept_once_persists_job_and_one_workflow_outbox_event(database):
    url, adapter = database
    job = new_job()
    assert adapter.accept_once(job) == job
    assert adapter.accept_once(job) == job
    assert adapter.load(tenant_id=job.tenant_id, job_id=job.job_id) == job
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM workflow_outbox WHERE outbox_id=%s",
                        (f"multimodal:{job.job_id}:0",))
            assert cur.fetchone()[0] == 1


def test_transitions_are_atomic_tenant_isolated_and_versioned(database):
    url, adapter = database
    job = new_job()
    adapter.accept_once(job)
    with pytest.raises(KeyError):
        adapter.transition_and_enqueue_event(
            tenant_id="other", job_id=job.job_id, expected_version=0,
            new_status=JobStatus.STARTED, event_id=f"other-{uuid4().hex}",
        )
    started = adapter.transition_and_enqueue_event(
        tenant_id=job.tenant_id, job_id=job.job_id, expected_version=0,
        new_status=JobStatus.STARTED, event_id=f"start-{uuid4().hex}",
    )
    assert started.version == 1
    with pytest.raises(ValueError, match="Stale"):
        adapter.transition_and_enqueue_event(
            tenant_id=job.tenant_id, job_id=job.job_id, expected_version=0,
            new_status=JobStatus.FAILED, event_id=f"stale-{uuid4().hex}",
        )
    assert adapter.load(tenant_id=job.tenant_id, job_id=job.job_id) == started


def test_failed_transition_does_not_publish_an_event(database):
    url, adapter = database
    job = new_job()
    adapter.accept_once(job)
    eid = f"invalid-{uuid4().hex}"
    with pytest.raises(ValueError, match="Invalid"):
        adapter.transition_and_enqueue_event(
            tenant_id=job.tenant_id, job_id=job.job_id, expected_version=0,
            new_status=JobStatus.COMPLETED, event_id=eid,
        )
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM workflow_outbox WHERE outbox_id=%s", (eid,))
            assert cur.fetchone()[0] == 0
