from datetime import datetime, timezone

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.workflow.in_memory_unit_of_work import (
    InMemoryWorkflowUnitOfWork,
)
from rkjo_kernel.workflow.outbox import OutboxMessage


def _outbox_message(
    outbox_id: str = "outbox-1",
) -> OutboxMessage:
    return OutboxMessage(
        outbox_id=outbox_id,
        queue_name="agent.queue",
        message=AgentMessage(
            source="rkjo.workflow",
            target="agent.one",
            message_type="workflow.step.execute",
            payload={"value": 1},
        ),
        created_at=datetime.now(timezone.utc),
    )


def test_commit_keeps_inbox_and_outbox_changes():
    uow = InMemoryWorkflowUnitOfWork()

    with uow:
        uow.inbox.mark_processed("message-1")
        uow.outbox.add(
            _outbox_message()
        )
        uow.commit()

    assert uow.inbox.contains("message-1")
    assert len(uow.outbox.pending()) == 1


def test_uncommitted_transaction_rolls_back():
    uow = InMemoryWorkflowUnitOfWork()

    with uow:
        uow.inbox.mark_processed("message-1")
        uow.outbox.add(
            _outbox_message()
        )

    assert not uow.inbox.contains("message-1")
    assert uow.outbox.pending() == []


def test_exception_rolls_back_transaction():
    uow = InMemoryWorkflowUnitOfWork()

    try:
        with uow:
            uow.inbox.mark_processed("message-1")
            uow.outbox.add(
                _outbox_message()
            )
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert not uow.inbox.contains("message-1")
    assert uow.outbox.pending() == []


def test_mark_published_removes_message_from_pending():
    uow = InMemoryWorkflowUnitOfWork()

    message = _outbox_message()

    with uow:
        uow.outbox.add(message)
        uow.commit()

    assert len(uow.outbox.pending()) == 1

    with uow:
        uow.outbox.mark_published(
            message.outbox_id
        )
        uow.commit()

    assert uow.outbox.pending() == []


def test_rollback_preserves_store_identity():
    uow = InMemoryWorkflowUnitOfWork()

    workflows_ref = uow.workflows
    inbox_ref = uow.inbox
    outbox_ref = uow.outbox

    with uow:
        uow.inbox.mark_processed(
            "rollback-check"
        )
        uow.outbox.add(
            _outbox_message("rollback-outbox")
        )

    assert uow.workflows is workflows_ref
    assert uow.inbox is inbox_ref
    assert uow.outbox is outbox_ref

    assert not inbox_ref.contains(
        "rollback-check"
    )
    assert outbox_ref.pending() == []
