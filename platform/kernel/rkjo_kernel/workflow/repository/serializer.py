"""Serialization helpers for workflow persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from rkjo_kernel.workflow.models.step_status import StepStatus
from rkjo_kernel.workflow.models.workflow_context import WorkflowContext
from rkjo_kernel.workflow.models.workflow_definition import WorkflowDefinition
from rkjo_kernel.workflow.models.workflow_execution import WorkflowExecution
from rkjo_kernel.workflow.models.workflow_status import WorkflowStatus
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep


def _datetime_to_string(
    value: datetime | None,
) -> str | None:
    if value is None:
        return None

    return value.isoformat()


def _datetime_from_string(
    value: str | None,
) -> datetime | None:
    if value is None:
        return None

    return datetime.fromisoformat(value)


def workflow_execution_to_dict(
    execution: WorkflowExecution,
) -> dict[str, Any]:
    """Serialize WorkflowExecution to JSON-compatible data."""

    return {
        "execution_id": execution.execution_id,
        "status": execution.status.value,
        "current_step_id": execution.current_step_id,
        "error": execution.error,
        "created_at": _datetime_to_string(
            execution.created_at
        ),
        "started_at": _datetime_to_string(
            execution.started_at
        ),
        "completed_at": _datetime_to_string(
            execution.completed_at
        ),
        "metadata": execution.metadata,
        "context": execution.context.snapshot(),
        "definition": {
            "workflow_id": execution.definition.workflow_id,
            "name": execution.definition.name,
            "version": execution.definition.version,
            "description": execution.definition.description,
            "metadata": execution.definition.metadata,
            "steps": [
                {
                    "step_id": step.step_id,
                    "name": step.name,
                    "agent_name": step.agent_name,
                    "capability_name": step.capability_name,
                    "description": step.description,
                    "position": step.position,
                    "input_mapping": step.input_mapping,
                    "metadata": step.metadata,
                    "status": step.status.value,
                    "output": step.output,
                    "error": step.error,
                    "started_at": _datetime_to_string(
                        step.started_at
                    ),
                    "completed_at": _datetime_to_string(
                        step.completed_at
                    ),
                }
                for step in execution.definition.steps
            ],
        },
    }


def workflow_execution_from_dict(
    data: dict[str, Any],
) -> WorkflowExecution:
    """Rebuild WorkflowExecution from persisted JSON data."""

    definition_data = data["definition"]

    steps = [
        WorkflowStep(
            step_id=step["step_id"],
            name=step["name"],
            agent_name=step.get("agent_name"),
            capability_name=step.get("capability_name"),
            description=step.get("description"),
            position=step.get("position", 0),
            input_mapping=dict(
                step.get("input_mapping") or {}
            ),
            metadata=dict(
                step.get("metadata") or {}
            ),
            status=StepStatus(step["status"]),
            output=step.get("output"),
            error=step.get("error"),
            started_at=_datetime_from_string(
                step.get("started_at")
            ),
            completed_at=_datetime_from_string(
                step.get("completed_at")
            ),
        )
        for step in definition_data["steps"]
    ]

    definition = WorkflowDefinition(
        workflow_id=definition_data["workflow_id"],
        name=definition_data["name"],
        version=definition_data.get(
            "version",
            "1.0.0",
        ),
        description=definition_data.get(
            "description"
        ),
        steps=steps,
        metadata=dict(
            definition_data.get("metadata") or {}
        ),
    )

    context_data = data.get("context") or {}

    context = WorkflowContext(
        input_data=dict(
            context_data.get("input_data") or {}
        ),
        variables=dict(
            context_data.get("variables") or {}
        ),
        outputs=dict(
            context_data.get("outputs") or {}
        ),
        metadata=dict(
            context_data.get("metadata") or {}
        ),
    )

    return WorkflowExecution(
        definition=definition,
        context=context,
        execution_id=data["execution_id"],
        status=WorkflowStatus(data["status"]),
        current_step_id=data.get("current_step_id"),
        error=data.get("error"),
        created_at=_datetime_from_string(
            data["created_at"]
        ),
        started_at=_datetime_from_string(
            data.get("started_at")
        ),
        completed_at=_datetime_from_string(
            data.get("completed_at")
        ),
        metadata=dict(
            data.get("metadata") or {}
        ),
    )
