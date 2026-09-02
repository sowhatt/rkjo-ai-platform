import pytest

from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.services.registry_service import (
    RegistryService,
)
from rkjo_kernel.workflow.agent_routing import (
    WorkflowAgentRouter,
)
from rkjo_kernel.workflow.async_dispatch import (
    AsyncWorkflowDispatcher,
)
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.in_memory_unit_of_work import (
    InMemoryWorkflowUnitOfWork,
)
from rkjo_kernel.workflow.models.workflow_definition import (
    WorkflowDefinition,
)
from rkjo_kernel.workflow.models.workflow_status import (
    WorkflowStatus,
)
from rkjo_kernel.workflow.models.workflow_step import (
    WorkflowStep,
)
from rkjo_kernel.workflow.transactional_result_handler import (
    TransactionalWorkflowResultHandler,
)


class NoopBus(EventBus):
    """Bus required by dispatcher; prepare() must not publish."""

    def __init__(self):
        self.published = []

    def publish(self, queue_name, message):
        pass

    def consume(self, queue_name, callback):
        pass

    def publish_agent_message(
        self,
        queue_name,
        message,
    ):
        self.published.append(
            (queue_name, message)
        )

    def consume_agent_messages(
        self,
        queue_name,
        callback,
    ):
        pass

    def close(self):
        pass


def make_environment(
    *,
    steps=2,
):
    uow = InMemoryWorkflowUnitOfWork()

    definition_steps = [
        WorkflowStep(
            step_id="step-1",
            name="Step 1",
            agent_name="agent.one",
            position=0,
        )
    ]

    if steps == 2:
        definition_steps.append(
            WorkflowStep(
                step_id="step-2",
                name="Step 2",
                agent_name="agent.two",
                position=1,
            )
        )

    definition = WorkflowDefinition(
        workflow_id="transactional-workflow",
        name="Transactional Workflow",
        steps=definition_steps,
    )

    with uow:
        engine = WorkflowEngine(
            repository=uow.workflows,
        )

        execution = engine.create_execution(
            definition,
            execution_id="exec-transactional",
        )

        engine.start(execution)
        engine.start_next_step(execution)

        uow.commit()

    registry = AgentRegistry()
    registry_service = RegistryService(
        registry=registry
    )

    if steps == 2:
        registry_service.register_agent(
            AgentDescriptor(
                name="agent.two",
                display_name="Agent Two",
                product="RKJO",
                queue_name="agent.two.queue",
                status=AgentStatus.AVAILABLE,
            )
        )

    bus = NoopBus()

    handler = TransactionalWorkflowResultHandler(
        uow_factory=lambda: uow,
        router=WorkflowAgentRouter(
            registry_service=registry_service
        ),
        dispatcher=AsyncWorkflowDispatcher(
            event_bus=bus
        ),
        reply_queue="rkjo.workflow.results",
    )

    return uow, bus, handler


def make_success_message(
    *,
    message_id="result-001",
):
    return AgentMessage(
        message_id=message_id,
        correlation_id="corr-001",
        source="agent.one",
        target="rkjo.workflow",
        message_type="workflow.step.result",
        payload={
            "success": True,
            "result": {
                "value": "step-one-result",
            },
        },
        metadata={
            "workflow_execution_id": (
                "exec-transactional"
            ),
            "workflow_step_id": "step-1",
        },
    )


def test_success_atomically_updates_workflow_inbox_and_outbox():
    uow, bus, handler = make_environment()

    message = make_success_message()

    handler.handle(message)

    with uow:
        execution = uow.workflows.get(
            "exec-transactional"
        )

        assert execution is not None
        assert execution.current_step_id == "step-2"

        assert execution.context.outputs[
            "step-1"
        ] == {
            "value": "step-one-result",
        }

        assert uow.inbox.contains(
            message.message_id
        )

        pending = uow.outbox.pending()

        assert len(pending) == 1

        outbox_message = pending[0]

        assert (
            outbox_message.queue_name
            == "agent.two.queue"
        )

        assert (
            outbox_message.message.target
            == "agent.two"
        )

        assert (
            outbox_message.message.correlation_id
            == "corr-001"
        )

        assert (
            outbox_message.message.metadata[
                "workflow_step_id"
            ]
            == "step-2"
        )

    # prepare_next() must not publish directly.
    assert bus.published == []


def test_duplicate_message_is_noop():
    uow, bus, handler = make_environment()

    message = make_success_message()

    handler.handle(message)
    handler.handle(message)

    with uow:
        execution = uow.workflows.get(
            "exec-transactional"
        )

        assert execution is not None
        assert execution.current_step_id == "step-2"

        pending = uow.outbox.pending()

        assert len(pending) == 1

    assert bus.published == []


def test_last_step_success_completes_without_outbox():
    uow, bus, handler = make_environment(
        steps=1
    )

    message = make_success_message()

    handler.handle(message)

    with uow:
        execution = uow.workflows.get(
            "exec-transactional"
        )

        assert execution is not None
        assert (
            execution.status
            == WorkflowStatus.COMPLETED
        )

        assert uow.inbox.contains(
            message.message_id
        )

        assert uow.outbox.pending() == []

    assert bus.published == []


def test_failure_fails_workflow_without_outbox():
    uow, bus, handler = make_environment()

    message = AgentMessage(
        message_id="result-failure",
        correlation_id="corr-failure",
        source="agent.one",
        target="rkjo.workflow",
        message_type="workflow.step.result",
        payload={
            "success": False,
            "error": "agent failed",
        },
        metadata={
            "workflow_execution_id": (
                "exec-transactional"
            ),
            "workflow_step_id": "step-1",
        },
    )

    handler.handle(message)

    with uow:
        execution = uow.workflows.get(
            "exec-transactional"
        )

        assert execution is not None
        assert execution.status == WorkflowStatus.FAILED
        assert execution.error == "agent failed"

        assert uow.inbox.contains(
            message.message_id
        )

        assert uow.outbox.pending() == []

    assert bus.published == []


def test_prepare_failure_rolls_back_entire_transaction():
    uow, bus, handler = make_environment()

    # Remove the only routable destination.
    empty_registry = AgentRegistry()

    handler.router = WorkflowAgentRouter(
        registry_service=RegistryService(
            registry=empty_registry
        )
    )

    message = make_success_message(
        message_id="result-routing-failure"
    )

    with pytest.raises(LookupError):
        handler.handle(message)

    with uow:
        execution = uow.workflows.get(
            "exec-transactional"
        )

        assert execution is not None

        # Entire result processing was rolled back.
        assert execution.current_step_id == "step-1"

        assert execution.context.outputs == {}

        assert not uow.inbox.contains(
            message.message_id
        )

        assert uow.outbox.pending() == []

    assert bus.published == []


def test_conflicting_stale_result_is_rejected_and_not_consumed():
    uow, bus, handler = make_environment()

    message = make_success_message(
        message_id="result-original"
    )

    handler.handle(message)

    conflicting = AgentMessage(
        message_id="result-conflicting",
        correlation_id="corr-001",
        source="agent.one",
        target="rkjo.workflow",
        message_type="workflow.step.result",
        payload={
            "success": True,
            "result": {
                "value": "different-result",
            },
        },
        metadata={
            "workflow_execution_id": (
                "exec-transactional"
            ),
            "workflow_step_id": "step-1",
        },
    )

    with pytest.raises(
        RuntimeError,
        match="Workflow result does not match",
    ):
        handler.handle(conflicting)

    with uow:
        assert not uow.inbox.contains(
            conflicting.message_id
        )

        assert len(
            uow.outbox.pending()
        ) == 1

    assert bus.published == []
