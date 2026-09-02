"""Transactional processing of asynchronous workflow results."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.workflow.agent_routing import (
    WorkflowAgentRouter,
)
from rkjo_kernel.workflow.async_coordinator import (
    AsyncWorkflowCoordinator,
)
from rkjo_kernel.workflow.async_dispatch import (
    AsyncWorkflowDispatcher,
)
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.outbox import OutboxMessage
from rkjo_kernel.workflow.unit_of_work import (
    WorkflowUnitOfWork,
)


WorkflowUnitOfWorkFactory = Callable[
    [],
    WorkflowUnitOfWork,
]


class TransactionalWorkflowResultHandler:
    """Apply workflow results atomically with inbox and outbox."""

    def __init__(
        self,
        *,
        uow_factory: WorkflowUnitOfWorkFactory,
        router: WorkflowAgentRouter,
        dispatcher: AsyncWorkflowDispatcher,
        reply_queue: str,
    ) -> None:
        if not reply_queue or not reply_queue.strip():
            raise ValueError(
                "reply_queue must not be empty."
            )

        self.uow_factory = uow_factory
        self.router = router
        self.dispatcher = dispatcher
        self.reply_queue = reply_queue.strip()

    def handle(
        self,
        message: AgentMessage,
    ) -> None:
        """Process one workflow.step.result transactionally."""

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

        with self.uow_factory() as uow:
            if uow.inbox.contains(
                message.message_id
            ):
                return

            engine = WorkflowEngine(
                repository=uow.workflows,
            )

            coordinator = AsyncWorkflowCoordinator(
                engine=engine,
                router=self.router,
                dispatcher=self.dispatcher,
                reply_queue=self.reply_queue,
            )

            execution = engine.load_execution(
                execution_id
            )

            if execution.current_step_id != step_id:
                self._handle_stale_result(
                    engine=engine,
                    coordinator=coordinator,
                    execution=execution,
                    message=message,
                    step_id=step_id,
                    uow=uow,
                )
                return

            success = bool(
                message.payload.get("success")
            )

            if success:
                engine.complete_current_step(
                    execution,
                    output=message.payload.get(
                        "result"
                    ),
                )

                next_step = engine.get_next_step(
                    execution
                )

                if next_step is None:
                    engine.complete(
                        execution
                    )
                else:
                    self._prepare_next(
                        coordinator=coordinator,
                        execution=execution,
                        message=message,
                        uow=uow,
                    )

            else:
                error = str(
                    message.payload.get(
                        "error",
                        "Agent execution failed.",
                    )
                )

                engine.fail_current_step(
                    execution,
                    error=error,
                    fail_workflow=True,
                )

            uow.inbox.mark_processed(
                message.message_id
            )

            uow.commit()

    def _handle_stale_result(
        self,
        *,
        engine: WorkflowEngine,
        coordinator: AsyncWorkflowCoordinator,
        execution,
        message: AgentMessage,
        step_id: str,
        uow: WorkflowUnitOfWork,
    ) -> None:
        """Handle a result whose step is no longer current."""

        matching_step = next(
            (
                step
                for step in execution.definition.steps
                if step.step_id == step_id
            ),
            None,
        )

        already_applied = (
            matching_step is not None
            and getattr(
                matching_step.status,
                "value",
                matching_step.status,
            )
            == "completed"
            and bool(
                message.payload.get("success")
            )
            and matching_step.output
            == message.payload.get("result")
        )

        if not already_applied:
            raise RuntimeError(
                "Workflow result does not match the "
                "currently running step."
            )

        workflow_running = (
            getattr(
                execution.status,
                "value",
                execution.status,
            )
            == "running"
        )

        continuation_interrupted = (
            workflow_running
            and execution.current_step_id is None
            and engine.get_next_step(execution)
            is not None
        )

        if continuation_interrupted:
            self._prepare_next(
                coordinator=coordinator,
                execution=execution,
                message=message,
                uow=uow,
            )

        uow.inbox.mark_processed(
            message.message_id
        )

        uow.commit()

    @staticmethod
    def _prepare_next(
        *,
        coordinator: AsyncWorkflowCoordinator,
        execution,
        message: AgentMessage,
        uow: WorkflowUnitOfWork,
    ) -> None:
        """Prepare the next step and persist it in the outbox."""

        prepared = coordinator.prepare_next(
            execution,
            correlation_id=message.correlation_id,
        )

        if prepared is None:
            return

        uow.outbox.add(
            OutboxMessage(
                outbox_id=prepared.message.message_id,
                queue_name=prepared.queue_name,
                message=prepared.message,
                created_at=datetime.now(
                    timezone.utc
                ),
            )
        )
