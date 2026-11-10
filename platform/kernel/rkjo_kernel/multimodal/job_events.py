"""Transactional multimodal lifecycle-event routing to the existing RKJO outbox."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.multimodal.jobs import DurableJobPort, JobStatus
from rkjo_kernel.workflow.outbox import OutboxMessage
from rkjo_kernel.workflow.unit_of_work import WorkflowUnitOfWork


class MultimodalJobEventHandler:
    """Idempotently request user notifications without re-running ingestion jobs.

    The channel delivery worker remains independent and must deduplicate using
    the resulting message_id. The inbox and notification outbox share a UoW.
    """

    def __init__(
        self,
        *,
        jobs: DurableJobPort,
        uow_factory: Callable[[], WorkflowUnitOfWork],
        notification_queue: str = "rkjo.multimodal.notifications",
    ) -> None:
        if not notification_queue.strip():
            raise ValueError("Notification queue is required.")
        self.jobs = jobs
        self.uow_factory = uow_factory
        self.notification_queue = notification_queue

    def handle(self, message: AgentMessage) -> None:
        if message.source != "rkjo.multimodal" or message.message_type != "event":
            raise ValueError("Unsupported multimodal event.")
        payload = message.payload
        tenant_id = payload.get("tenant_id")
        job_id = payload.get("job_id")
        version = payload.get("version")
        try:
            status = JobStatus(payload.get("status"))
        except (ValueError, TypeError):
            raise ValueError("Invalid job event status.") from None
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("Job event requires tenant_id.")
        if not isinstance(job_id, str) or not job_id.strip():
            raise ValueError("Job event requires job_id.")
        if not isinstance(version, int) or isinstance(version, bool) or version < 0:
            raise ValueError("Job event requires a non-negative version.")
        if payload.get("event") != f"Job{status.value.capitalize()}":
            raise ValueError("Job event type and status mismatch.")
        job = self.jobs.load(tenant_id=tenant_id, job_id=job_id)
        if job is None:
            raise KeyError("Job not found in authenticated tenant.")
        if job.version < version:
            raise ValueError("Future job event version.")
        if job.version == version and job.status != status:
            raise ValueError("Job event contradicts persisted job status.")
        if message.correlation_id != job.correlation_id:
            raise ValueError("Job event correlation mismatch.")
        for key, expected in (
            ("tenant_id", job.tenant_id),
            ("mission_id", job.mission_id),
            ("trace_id", job.trace_id),
            ("channel", job.channel),
            ("recipient_ref", job.recipient_ref),
            ("idempotency_key", job.idempotency_key),
        ):
            if message.metadata.get(key) != expected:
                raise ValueError(f"Job event {key} mismatch.")
        # A previously completed job can still deliver an earlier Accepted
        # event. A contradictory historical event requires ledger verification.
        if version < job.version and status not in (JobStatus.ACCEPTED, JobStatus.STARTED):
            raise ValueError("Historical terminal event requires ledger verification.")

        with self.uow_factory() as uow:
            if uow.inbox.contains(message.message_id):
                return
            notify_id = f"multimodal:notify:{tenant_id}:{job_id}:{version}"
            notification = AgentMessage(
                message_id=notify_id,
                correlation_id=job.correlation_id,
                source="rkjo.multimodal.job_events",
                target="rkjo.multimodal.channel_delivery",
                message_type="multimodal.notification.requested",
                payload={
                    "job_id": job_id,
                    "status": status.value,
                    "event_version": version,
                },
                metadata={
                    "tenant_id": tenant_id,
                    "mission_id": job.mission_id,
                    "trace_id": job.trace_id,
                    "channel": job.channel,
                    "recipient_ref": job.recipient_ref,
                    "idempotency_key": job.idempotency_key,
                },
            )
            uow.outbox.add(OutboxMessage(
                outbox_id=notify_id,
                queue_name=self.notification_queue,
                message=notification,
                created_at=datetime.now(timezone.utc),
            ))
            uow.inbox.mark_processed(message.message_id)
            uow.commit()
