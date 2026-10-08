"""S31.2 ingestion lifecycle contracts; adapters must persist events transactionally."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class JobStatus(str, Enum):
    ACCEPTED = "accepted"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


_ALLOWED: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.ACCEPTED: frozenset({JobStatus.STARTED, JobStatus.FAILED}),
    JobStatus.STARTED: frozenset({JobStatus.COMPLETED, JobStatus.FAILED}),
    JobStatus.COMPLETED: frozenset(),
    JobStatus.FAILED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class IngestionJob:
    job_id: str
    tenant_id: str
    idempotency_key: str
    channel: str
    recipient_ref: str
    correlation_id: str
    mission_id: str | None = None
    trace_id: str | None = None
    status: JobStatus = JobStatus.ACCEPTED
    version: int = 0

    def __post_init__(self) -> None:
        if not all((self.job_id.strip(), self.tenant_id.strip(),
                    self.idempotency_key.strip(), self.channel.strip(),
                    self.recipient_ref.strip(), self.correlation_id.strip())):
            raise ValueError("Job identity, idempotency and channel context are required.")
        if self.version < 0:
            raise ValueError("Job version must be non-negative.")

    def transition(self, new_status: JobStatus) -> "IngestionJob":
        if new_status not in _ALLOWED[self.status]:
            raise ValueError(f"Invalid job transition: {self.status} -> {new_status}")
        from dataclasses import replace
        return replace(self, status=new_status, version=self.version + 1)


@dataclass(frozen=True, slots=True)
class JobLifecycleEvent:
    event_id: str
    job_id: str
    tenant_id: str
    status: JobStatus
    version: int
    correlation_id: str

    def __post_init__(self) -> None:
        if not all((self.event_id.strip(), self.job_id.strip(),
                    self.tenant_id.strip(), self.correlation_id.strip())):
            raise ValueError("Event identity fields cannot be blank.")
        if self.version < 0:
            raise ValueError("Event version must be non-negative.")


class DurableJobPort(Protocol):
    """Adapter must use atomic CAS/version checks for cross-worker transitions."""
    def accept_once(self, job: IngestionJob) -> IngestionJob: ...
    def load(self, *, tenant_id: str, job_id: str) -> IngestionJob | None: ...
    def transition_and_enqueue_event(
        self, *, tenant_id: str, job_id: str, expected_version: int,
        new_status: JobStatus, event_id: str,
    ) -> IngestionJob: ...


class NotificationOutboxPort(Protocol):
    """Notification delivery retries are independent of job execution."""
    def enqueue_once(self, *, tenant_id: str, job_id: str,
                     event_id: str, channel: str, recipient_ref: str) -> None: ...
