from dataclasses import replace

import pytest

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.multimodal.job_events import MultimodalJobEventHandler
from rkjo_kernel.multimodal.jobs import IngestionJob, JobStatus
from rkjo_kernel.workflow.in_memory_unit_of_work import InMemoryWorkflowUnitOfWork


def job():
    return IngestionJob(
        job_id="j1", tenant_id="tenant-a", idempotency_key="idem",
        channel="whatsapp", recipient_ref="private-ref", correlation_id="corr",
        mission_id="m", trace_id="t",
    )


class Jobs:
    def __init__(self, item):
        self.item = item

    def load(self, *, tenant_id, job_id):
        if tenant_id == self.item.tenant_id and job_id == self.item.job_id:
            return self.item
        return None


def event(item, *, status=JobStatus.ACCEPTED, version=0, message_id="e1"):
    return AgentMessage(
        message_id=message_id, correlation_id=item.correlation_id,
        source="rkjo.multimodal", target="rkjo.multimodal.job_events",
        message_type="event",
        payload={"event": f"Job{status.value.capitalize()}",
                 "job_id": item.job_id, "tenant_id": item.tenant_id,
                 "status": status.value, "version": version},
        metadata={"tenant_id": item.tenant_id, "mission_id": item.mission_id,
                  "trace_id": item.trace_id, "channel": item.channel,
                  "recipient_ref": item.recipient_ref,
                  "idempotency_key": item.idempotency_key},
    )


def test_event_routes_accepted_notification_and_deduplicates():
    item = job()
    uow = InMemoryWorkflowUnitOfWork()
    handler = MultimodalJobEventHandler(jobs=Jobs(item), uow_factory=lambda: uow)
    handler.handle(event(item))
    handler.handle(event(item))
    pending = uow.outbox.pending()
    assert len(pending) == 1
    assert pending[0].message.metadata["channel"] == "whatsapp"
    assert pending[0].message.payload["status"] == "accepted"


def test_terminal_failure_routes_independently():
    item = job().transition(JobStatus.FAILED)
    uow = InMemoryWorkflowUnitOfWork()
    handler = MultimodalJobEventHandler(jobs=Jobs(item), uow_factory=lambda: uow)
    handler.handle(event(item, status=JobStatus.FAILED, version=1))
    assert uow.outbox.pending()[0].message.payload["status"] == "failed"
    assert item.status == JobStatus.FAILED


def test_spoofed_tenant_is_rejected_without_outbox():
    item = job()
    uow = InMemoryWorkflowUnitOfWork()
    handler = MultimodalJobEventHandler(jobs=Jobs(item), uow_factory=lambda: uow)
    bad = event(item)
    bad.payload["tenant_id"] = "tenant-b"
    with pytest.raises(KeyError):
        handler.handle(bad)
    assert uow.outbox.pending() == []


def test_mismatched_correlation_or_channel_is_rejected():
    item = job()
    uow = InMemoryWorkflowUnitOfWork()
    handler = MultimodalJobEventHandler(jobs=Jobs(item), uow_factory=lambda: uow)
    bad = event(item)
    bad.metadata["channel"] = "api"
    with pytest.raises(ValueError, match="channel"):
        handler.handle(bad)
    bad = event(item, message_id="e2")
    bad.correlation_id = "wrong"
    with pytest.raises(ValueError, match="correlation"):
        handler.handle(bad)
    assert uow.outbox.pending() == []


def test_future_version_rejected():
    item = job()
    handler = MultimodalJobEventHandler(
        jobs=Jobs(item), uow_factory=InMemoryWorkflowUnitOfWork,
    )
    with pytest.raises(ValueError, match="Future"):
        handler.handle(event(item, version=2))
