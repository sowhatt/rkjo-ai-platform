"""Asynchronous workflow step dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.workflow.models.workflow_context import WorkflowContext
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep


@dataclass(frozen=True, slots=True)
class AsyncDispatchResult:
    """Result returned after a workflow step is queued."""

    message_id: str
    correlation_id: str
    queue_name: str
    step_id: str


class AsyncWorkflowDispatcher:
    """Publish workflow step missions through EventBus."""

    def __init__(
        self,
        *,
        event_bus: EventBus,
        source: str = "rkjo.workflow",
    ) -> None:
        self.event_bus = event_bus
        self.source = source

    def dispatch(
        self,
        *,
        step: WorkflowStep,
        context: WorkflowContext,
        queue_name: str,
        execution_id: str,
        correlation_id: str | None = None,
    ) -> AsyncDispatchResult:
        """Queue one workflow step for asynchronous execution."""

        if not queue_name or not queue_name.strip():
            raise ValueError(
                "queue_name must not be empty."
            )

        correlation = (
            correlation_id
            or str(uuid4())
        )

        message = AgentMessage(
            source=self.source,
            target=step.routing_target,
            message_type="workflow.step.execute",
            correlation_id=correlation,
            payload={
                "input_data": context.input_data,
                "variables": context.variables,
                "outputs": context.outputs,
            },
            metadata={
                **context.metadata,
                "workflow_execution_id": execution_id,
                "workflow_step_id": step.step_id,
                "capability_name": step.capability_name,
            },
        )

        self.event_bus.publish_agent_message(
            queue_name=queue_name,
            message=message,
        )

        return AsyncDispatchResult(
            message_id=message.message_id,
            correlation_id=message.correlation_id,
            queue_name=queue_name,
            step_id=step.step_id,
        )
