from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.idempotency import (
    InMemoryProcessedMessageStore,
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
from rkjo_kernel.workflow.repository.memory import (
    InMemoryWorkflowRepository,
)
from rkjo_kernel.workflow.result_handler import (
    WorkflowResultHandler,
)


def make_engine():
    repository = InMemoryWorkflowRepository()

    engine = WorkflowEngine(
        repository=repository
    )

    definition = WorkflowDefinition(
        workflow_id="workflow-idempotency",
        name="Idempotency Workflow",
        steps=[
            WorkflowStep(
                step_id="weather",
                name="Weather",
                capability_name="weather.analysis",
            )
        ],
    )

    execution = engine.create_execution(
        definition,
        execution_id="exec-idempotency-001",
    )

    engine.start(execution)
    engine.start_next_step(execution)

    return engine, repository


def make_result_message():
    return AgentMessage(
        message_id="result-message-001",
        correlation_id="corr-001",
        source="weather.agent",
        target="rkjo.workflow",
        message_type="workflow.step.result",
        payload={
            "success": True,
            "result": {
                "temperature": 31,
            },
        },
        metadata={
            "workflow_execution_id": (
                "exec-idempotency-001"
            ),
            "workflow_step_id": "weather",
        },
    )


def test_duplicate_result_is_applied_only_once():
    engine, repository = make_engine()

    store = InMemoryProcessedMessageStore()

    handler = WorkflowResultHandler(
        engine=engine,
        processed_messages=store,
    )

    message = make_result_message()

    handler.handle(message)
    handler.handle(message)

    execution = repository.get(
        "exec-idempotency-001"
    )

    assert execution is not None

    assert execution.status == (
        WorkflowStatus.COMPLETED
    )

    assert execution.context.outputs == {
        "weather": {
            "temperature": 31,
        }
    }

    assert store.contains(
        message.message_id
    )


def test_different_result_message_is_not_ignored():
    engine, _ = make_engine()

    store = InMemoryProcessedMessageStore()

    handler = WorkflowResultHandler(
        engine=engine,
        processed_messages=store,
    )

    first = make_result_message()

    handler.handle(first)

    second = first.model_copy(
        update={
            "message_id": "result-message-002"
        }
    )

    assert store.contains(
        first.message_id
    )

    assert not store.contains(
        second.message_id
    )


def test_handler_remains_compatible_without_idempotency_store():
    engine, repository = make_engine()

    handler = WorkflowResultHandler(
        engine=engine
    )

    message = make_result_message()

    handler.handle(message)

    execution = repository.get(
        "exec-idempotency-001"
    )

    assert execution is not None
    assert execution.status == (
        WorkflowStatus.COMPLETED
    )


def test_store_tracks_processed_messages():
    store = InMemoryProcessedMessageStore()

    assert not store.contains("m-1")

    store.mark_processed("m-1")

    assert store.contains("m-1")
