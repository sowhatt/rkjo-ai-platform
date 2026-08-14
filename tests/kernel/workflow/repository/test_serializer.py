from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.models.workflow_definition import WorkflowDefinition
from rkjo_kernel.workflow.models.workflow_status import WorkflowStatus
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep
from rkjo_kernel.workflow.repository.serializer import (
    workflow_execution_from_dict,
    workflow_execution_to_dict,
)


def make_definition() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id="workflow-postgres",
        name="PostgreSQL Workflow",
        steps=[
            WorkflowStep(
                step_id="weather",
                name="Weather Analysis",
                capability_name="weather.analysis",
                position=0,
            ),
            WorkflowStep(
                step_id="risk",
                name="Risk Analysis",
                capability_name="risk.analysis",
                position=1,
            ),
        ],
    )


def test_execution_serialization_round_trip():
    engine = WorkflowEngine()

    execution = engine.create_execution(
        make_definition(),
        execution_id="execution-postgres-001",
        input_data={
            "parcel_id": "P-100",
        },
        metadata={
            "product": "ADIP",
        },
    )

    engine.start(execution)
    engine.start_next_step(execution)
    engine.complete_current_step(
        execution,
        output={
            "rainfall": 12.5,
        },
    )

    payload = workflow_execution_to_dict(
        execution
    )

    restored = workflow_execution_from_dict(
        payload
    )

    assert restored.execution_id == execution.execution_id
    assert restored.status == WorkflowStatus.RUNNING

    assert restored.context.input_data == {
        "parcel_id": "P-100"
    }

    assert restored.context.outputs == {
        "weather": {
            "rainfall": 12.5
        }
    }

    assert restored.metadata == {
        "product": "ADIP"
    }

    assert len(restored.definition.steps) == 2

    assert (
        restored.definition.steps[0]
        .capability_name
        == "weather.analysis"
    )

    assert (
        restored.definition.steps[0]
        .status.value
        == "completed"
    )


def test_execution_serialization_preserves_timestamps():
    engine = WorkflowEngine()

    execution = engine.create_execution(
        make_definition(),
        execution_id="execution-postgres-002",
    )

    engine.start(execution)

    payload = workflow_execution_to_dict(
        execution
    )

    restored = workflow_execution_from_dict(
        payload
    )

    assert restored.created_at == execution.created_at
    assert restored.started_at == execution.started_at
