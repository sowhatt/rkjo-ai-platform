"""Apply asynchronous agent results to persisted workflows."""

from __future__ import annotations

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.workflow.engine import WorkflowEngine


class WorkflowResultHandler:
    """Update workflow state from asynchronous agent results."""

    def __init__(
        self,
        *,
        engine: WorkflowEngine,
    ) -> None:
        self.engine = engine

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

            if self.engine.get_next_step(
                execution
            ) is None:
                self.engine.complete(
                    execution
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
