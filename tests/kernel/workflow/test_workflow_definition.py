import pytest

from rkjo_kernel.workflow import (
    InvalidWorkflowDefinitionError,
    WorkflowDefinition,
    WorkflowStep,
)


def create_step(step_id, position):
    return WorkflowStep(
        step_id=step_id,
        name=f"Step {step_id}",
        agent_name=f"{step_id}_agent",
        position=position,
    )


def test_definition_orders_steps_by_position():
    definition = WorkflowDefinition(
        workflow_id="customer.onboarding",
        name="Customer onboarding",
        steps=[
            create_step("execute", 2),
            create_step("validate", 0),
            create_step("assign", 1),
        ],
    )

    assert [
        step.step_id
        for step in definition.steps
    ] == [
        "validate",
        "assign",
        "execute",
    ]


def test_definition_rejects_duplicate_step_ids():
    with pytest.raises(InvalidWorkflowDefinitionError):
        WorkflowDefinition(
            workflow_id="duplicate.ids",
            name="Duplicate identifiers",
            steps=[
                create_step("validate", 0),
                create_step("validate", 1),
            ],
        )


def test_definition_rejects_duplicate_positions():
    with pytest.raises(InvalidWorkflowDefinitionError):
        WorkflowDefinition(
            workflow_id="duplicate.positions",
            name="Duplicate positions",
            steps=[
                create_step("validate", 0),
                create_step("execute", 0),
            ],
        )


def test_definition_adds_and_retrieves_step():
    definition = WorkflowDefinition(
        workflow_id="dynamic.workflow",
        name="Dynamic workflow",
    )

    step = create_step("validate", 0)
    definition.add_step(step)

    assert definition.get_step("validate") is step
    assert definition.get_step("unknown") is None
