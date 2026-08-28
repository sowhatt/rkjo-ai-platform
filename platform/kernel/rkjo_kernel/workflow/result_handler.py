"""Apply asynchronous agent results to persisted workflows."""

from __future__ import annotations

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.workflow.async_coordinator import AsyncWorkflowCoordinator
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.idempotency import ProcessedMessageStore


class WorkflowResultHandler:
    """Update workflow state from asynchronous agent results."""

    def __init__(
        self,
        *,
        engine: WorkflowEngine,
        processed_messages: ProcessedMessageStore | None = None,
        coordinator: AsyncWorkflowCoordinator | None = None,
    ) -> None:
        self.engine = engine
        self.processed_messages = processed_messages
        self.coordinator = coordinator

    def handle(
        self,
        message: AgentMessage,
    ) -> None:
        """Apply one workflow.step.result message."""

        if message.message_type != "workflow.step.result":
            raise ValueError(
                "Unsupported workflow result message type: "
                f"'{message.message_type}'."
            )

        if (
            self.processed_messages is not None
            and self.processed_messages.contains(
                message.message_id
            )
        ):
            return

        execution_id = message.metadata.get(
            "workflow_execution_id"
        )

        step_id = message.metadata.get(
            "workflow_step_id"
        )

        if not execution_id:
            raise ValueError(
                "workflow_execution_id is required."
            )

        if not step_id:
            raise ValueError(
                "workflow_step_id is required."
            )

        execution = self.engine.load_execution(
            execution_id
        )

        if execution.current_step_id != step_id:
            raise RuntimeError(
                "Workflow result does not match the "
                "currently running step."
            )

        success = bool(
            message.payload.get("success")
        )

        if success:
            self.engine.complete_current_step(
                execution,
                output=message.payload.get(
                    "result"
                ),
            )

            next_step = self.engine.get_next_step(
                execution
            )

            if next_step is None:
                self.engine.complete(
                    execution
                )

            elif self.coordinator is not None:
                self.coordinator.dispatch_next(
                    execution,
                    correlation_id=message.correlation_id,
                )

            self._mark_processed(
                message.message_id
            )

            return

        error = str(
            message.payload.get(
                "error",
                "Agent execution failed.",
            )
        )

        self.engine.fail_current_step(
            execution,
            error=error,
            fail_workflow=True,
        )

        self._mark_processed(
            message.message_id
        )

    def _mark_processed(
        self,
        message_id: str,
    ) -> None:
        if self.processed_messages is not None:
            self.processed_messages.mark_processed(
                message_id
            )
