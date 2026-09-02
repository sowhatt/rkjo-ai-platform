"""Coordinate asynchronous workflow progression."""

from __future__ import annotations

from dataclasses import dataclass

from rkjo_kernel.messages.agent_message import AgentMessage

from rkjo_kernel.workflow.agent_routing import WorkflowAgentRouter
from rkjo_kernel.workflow.async_dispatch import (
    AsyncDispatchResult,
    AsyncWorkflowDispatcher,
)
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.models.workflow_execution import (
    WorkflowExecution,
)


@dataclass(frozen=True, slots=True)
class PreparedWorkflowDispatch:
    """Workflow step prepared for durable publication."""

    queue_name: str
    message: AgentMessage
    step_id: str


class AsyncWorkflowCoordinator:
    """Start and dispatch the next asynchronous workflow step."""

    def __init__(
        self,
        *,
        engine: WorkflowEngine,
        router: WorkflowAgentRouter,
        dispatcher: AsyncWorkflowDispatcher,
        reply_queue: str,
    ) -> None:
        if not reply_queue or not reply_queue.strip():
            raise ValueError("reply_queue must not be empty.")

        self.engine = engine
        self.router = router
        self.dispatcher = dispatcher
        self.reply_queue = reply_queue.strip()

    def prepare_next(
        self,
        execution: WorkflowExecution,
        *,
        correlation_id: str | None = None,
    ) -> PreparedWorkflowDispatch | None:
        """Start, route and prepare the next step without publishing."""
        step = self.engine.start_next_step(execution)

        if step is None:
            return None

        try:
            route = self.router.resolve(step)

            queue_name, message = self.dispatcher.prepare(
                step=step,
                context=execution.context,
                queue_name=route.queue_name,
                execution_id=execution.execution_id,
                correlation_id=correlation_id,
                reply_queue=self.reply_queue,
                target_agent_name=route.agent_name,
            )

            return PreparedWorkflowDispatch(
                queue_name=queue_name,
                message=message,
                step_id=step.step_id,
            )

        except Exception:
            self.engine.fail_current_step(
                execution,
                error=(
                    "Failed to prepare asynchronous "
                    "workflow step."
                ),
                fail_workflow=True,
            )
            raise

    def dispatch_next(
        self,
        execution: WorkflowExecution,
        *,
        correlation_id: str | None = None,
    ) -> AsyncDispatchResult | None:
        """Start and dispatch the next pending step.

        Return None when the workflow has no remaining step.
        """
        step = self.engine.start_next_step(execution)

        if step is None:
            return None

        try:
            route = self.router.resolve(step)

            return self.dispatcher.dispatch(
                step=step,
                context=execution.context,
                queue_name=route.queue_name,
                execution_id=execution.execution_id,
                correlation_id=correlation_id,
                reply_queue=self.reply_queue,
                target_agent_name=route.agent_name,
            )
        except Exception:
            # start_next_step() has already persisted the RUNNING step.
            # Keep the workflow state consistent if routing/publication fails.
            self.engine.fail_current_step(
                execution,
                error="Failed to dispatch asynchronous workflow step.",
                fail_workflow=True,
            )
            raise
