"""Asynchronous workflow step dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.logging.logger import get_logger
from rkjo_kernel.logging.structured import structured_log
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.monitoring.metrics import MetricsRegistry
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
        metrics: MetricsRegistry | None = None,
    ) -> None:
        self.event_bus = event_bus
        self.source = source
        self.metrics = metrics
        self.logger = get_logger(
            "rkjo.workflow.dispatch"
        )

    def dispatch(
        self,
        *,
        step: WorkflowStep,
        context: WorkflowContext,
        queue_name: str,
        execution_id: str,
        correlation_id: str | None = None,
        reply_queue: str | None = None,
        target_agent_name: str | None = None,
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
            target=(
                target_agent_name
                or step.routing_target
            ),
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
                "reply_queue": reply_queue,
            },
        )

        self.event_bus.publish_agent_message(
            queue_name=queue_name,
            message=message,
        )

        if self.metrics is not None:
            self.metrics.increment(
                "workflow.dispatched"
            )

        structured_log(
            self.logger,
            event="workflow.dispatched",
            execution_id=execution_id,
            step_id=step.step_id,
            agent_name=message.target,
            queue_name=queue_name,
            message_id=message.message_id,
            correlation_id=message.correlation_id,
        )

        return AsyncDispatchResult(
            message_id=message.message_id,
            correlation_id=message.correlation_id,
            queue_name=queue_name,
            step_id=step.step_id,
        )
