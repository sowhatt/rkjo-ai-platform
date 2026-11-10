import pytest

from rkjo_kernel.multimodal.jobs import IngestionJob, JobLifecycleEvent, JobStatus


def job():
    return IngestionJob(
        job_id="job-1", tenant_id="tenant-a", idempotency_key="request-1",
        channel="whatsapp", recipient_ref="opaque-user", correlation_id="corr-1",
        mission_id="mission-1", trace_id="trace-1",
    )


def test_job_happy_path_and_versions():
    accepted = job()
    started = accepted.transition(JobStatus.STARTED)
    completed = started.transition(JobStatus.COMPLETED)
    assert [accepted.version, started.version, completed.version] == [0, 1, 2]
    assert completed.status == JobStatus.COMPLETED
    assert completed.tenant_id == accepted.tenant_id
    assert completed.recipient_ref == accepted.recipient_ref


def test_job_terminal_states_cannot_be_reopened():
    with pytest.raises(ValueError, match="Invalid"):
        job().transition(JobStatus.COMPLETED)
    with pytest.raises(ValueError, match="Invalid"):
        job().transition(JobStatus.FAILED).transition(JobStatus.STARTED)


def test_job_can_fail_after_start():
    assert job().transition(JobStatus.STARTED).transition(JobStatus.FAILED).version == 2


def test_job_requires_idempotency_and_channel_context():
    from dataclasses import replace
    with pytest.raises(ValueError, match="required"):
        replace(job(), idempotency_key="")
    with pytest.raises(ValueError, match="required"):
        replace(job(), recipient_ref="")


def test_lifecycle_event_retains_tenant_and_correlation():
    event = JobLifecycleEvent(
        event_id="evt-1", job_id="job-1", tenant_id="tenant-a",
        status=JobStatus.COMPLETED, version=2, correlation_id="corr-1",
    )
    assert (event.tenant_id, event.correlation_id, event.version) == ("tenant-a", "corr-1", 2)
