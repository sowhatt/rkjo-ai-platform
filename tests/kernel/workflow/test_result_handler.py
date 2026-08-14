from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.workflow.engine import WorkflowEngine
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
        workflow_id="workflow-result",
        name="Result Workflow",
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
        execution_id="exec-001",
    )

    engine.start(execution)
    engine.start_next_step(execution)

    return engine, repository


def test_success_result_completes_step_and_workflow():
    engine, repository = make_engine()

    handler = WorkflowResultHandler(
        engine=engine
    )

    message = AgentMessage(
        source="weather.agent",
        target="rkjo.workflow",
        message_type="workflow.step.result",
        correlation_id="corr-001",
        payload={
            "success": True,
            "result": {
                "temperature": 31,
            },
        },
        metadata={
            "workflow_execution_id": "exec-001",
            "workflow_step_id": "weather",
        },
    )

    handler.handle(message)

    execution = repository.get(
        "exec-001"
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


def test_failure_result_fails_workflow():
    engine, repository = make_engine()

    handler = WorkflowResultHandler(
        engine=engine
    )

    message = AgentMessage(
        source="weather.agent",
        target="rkjo.workflow",
        message_type="workflow.step.result",
        payload={
            "success": False,
            "error": "weather provider unavailable",
        },
        metadata={
            "workflow_execution_id": "exec-001",
            "workflow_step_id": "weather",
        },
    )

    handler.handle(message)

    execution = repository.get(
        "exec-001"
    )

    assert execution is not None
    assert execution.status == (
        WorkflowStatus.FAILED
    )

    assert execution.error == (
        "weather provider unavailable"
    )
