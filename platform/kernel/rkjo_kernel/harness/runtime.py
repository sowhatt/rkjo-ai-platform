"""Durable execution loop for RKJO agents."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Any, Callable, Protocol

from rkjo_kernel.harness.checkpoint import CheckpointService
from rkjo_kernel.harness.state import HarnessState, HarnessStateStatus, utc_now
from rkjo_kernel.mission.execution_context import ExecutionContext
from rkjo_kernel.runtime.retry_policy import RetryPolicy


@dataclass(frozen=True, slots=True)
class HarnessIterationResult:
    output: Any = None
    data: dict[str, Any] | None = None
    completed: bool = False
    suspended: bool = False

    def __post_init__(self) -> None:
        if self.completed and self.suspended:
            raise ValueError(
                "Harness iteration cannot be completed and suspended"
            )


class HarnessExecutor(Protocol):
    def __call__(
        self,
        *,
        state: HarnessState,
        context: ExecutionContext,
    ) -> HarnessIterationResult: ...


@dataclass(frozen=True, slots=True)
class HarnessPolicy:
    max_iterations: int = 100

    def __post_init__(self) -> None:
        if self.max_iterations < 1:
            raise ValueError("Harness max_iterations must be >= 1")


class AgentHarness:
    """Run one durable agent iteration and checkpoint every transition."""

    def __init__(
        self,
        *,
        checkpoints: CheckpointService,
        executor: HarnessExecutor,
        policy: HarnessPolicy | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self.checkpoints = checkpoints
        self.executor = executor
        self.policy = policy or HarnessPolicy()
        self.retry_policy = retry_policy

    def start(
        self,
        *,
        context: ExecutionContext,
        data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> HarnessState:
        tenant_id = self._tenant(context)
        state = HarnessState(
            tenant_id=tenant_id,
            mission_id=context.mission_id,
            trace_id=context.trace_id,
            status=HarnessStateStatus.CREATED,
            data=deepcopy(data or {}),
            metadata=deepcopy(metadata or {}),
        )
        return self.checkpoints.checkpoint(state)

    def resume(
        self,
        *,
        context: ExecutionContext,
        state_id: str | None = None,
    ) -> HarnessState:
        return self.checkpoints.resume(
            tenant_id=self._tenant(context),
            mission_id=context.mission_id,
            state_id=state_id,
        )

    def run_iteration(
        self,
        *,
        context: ExecutionContext,
        state: HarnessState,
    ) -> HarnessState:
        self._validate_identity(context, state)
        if state.iteration >= self.policy.max_iterations:
            limited = self.checkpoints.checkpoint(
                replace(
                    state,
                    status=HarnessStateStatus.FAILED,
                    metadata={
                        **deepcopy(state.metadata),
                        "termination_reason": "max_iterations_reached",
                    },
                    updated_at=utc_now(),
                )
            )
            raise RuntimeError(
                f"Harness iteration limit reached ({limited.iteration})"
            )
        if state.status in {
            HarnessStateStatus.COMPLETED,
            HarnessStateStatus.CANCELLED,
        }:
            raise ValueError(
                f"Cannot execute terminal harness state '{state.status.value}'"
            )

        running = self.checkpoints.checkpoint(
            replace(
                state,
                status=HarnessStateStatus.RUNNING,
                updated_at=utc_now(),
            )
        )

        try:
            result = self.executor(state=running, context=context)
        except Exception as exc:
            metadata = {
                **deepcopy(running.metadata),
                "last_error_type": type(exc).__name__,
                "last_error": str(exc),
            }
            if self.retry_policy is not None:
                attempt = int(metadata.get("retry_attempt", 1))
                decision = self.retry_policy.decide(
                    error=exc,
                    attempt=attempt,
                )
                metadata.update({
                    "retry_attempt": attempt + 1
                    if decision.should_retry else attempt,
                    "retry_should_retry": decision.should_retry,
                    "retry_delay_seconds": decision.delay_seconds,
                    "retry_reason": decision.reason,
                })
            failed = replace(
                running,
                status=HarnessStateStatus.FAILED,
                metadata=metadata,
                updated_at=utc_now(),
            )
            self.checkpoints.checkpoint(failed)
            raise

        next_data = deepcopy(running.data)
        if result.data is not None:
            next_data.update(deepcopy(result.data))
        next_data["last_output"] = deepcopy(result.output)

        status = HarnessStateStatus.RUNNING
        if result.completed:
            status = HarnessStateStatus.COMPLETED
        elif result.suspended:
            status = HarnessStateStatus.SUSPENDED

        return self.checkpoints.checkpoint(
            replace(
                running,
                status=status,
                iteration=running.iteration + 1,
                data=next_data,
                updated_at=utc_now(),
            )
        )

    def suspend(
        self,
        *,
        context: ExecutionContext,
        state: HarnessState,
        reason: str | None = None,
    ) -> HarnessState:
        self._validate_identity(context, state)
        if state.status in {
            HarnessStateStatus.COMPLETED,
            HarnessStateStatus.CANCELLED,
        }:
            raise ValueError("Cannot suspend terminal harness state")
        metadata = deepcopy(state.metadata)
        if reason is not None:
            metadata["suspension_reason"] = reason
        return self.checkpoints.checkpoint(
            replace(
                state,
                status=HarnessStateStatus.SUSPENDED,
                metadata=metadata,
                updated_at=utc_now(),
            )
        )

    def cancel(
        self,
        *,
        context: ExecutionContext,
        state: HarnessState,
        reason: str | None = None,
    ) -> HarnessState:
        self._validate_identity(context, state)
        if state.status is HarnessStateStatus.COMPLETED:
            raise ValueError("Cannot cancel completed harness state")
        if state.status is HarnessStateStatus.CANCELLED:
            return state
        metadata = deepcopy(state.metadata)
        if reason is not None:
            metadata["cancellation_reason"] = reason
        return self.checkpoints.checkpoint(
            replace(
                state,
                status=HarnessStateStatus.CANCELLED,
                metadata=metadata,
                updated_at=utc_now(),
            )
        )

    @staticmethod
    def _tenant(context: ExecutionContext) -> str:
        if context.tenant_id is None or not context.tenant_id.strip():
            raise ValueError("AgentHarness requires ExecutionContext tenant_id")
        return context.tenant_id

    @classmethod
    def _validate_identity(
        cls,
        context: ExecutionContext,
        state: HarnessState,
    ) -> None:
        if (
            state.tenant_id != cls._tenant(context)
            or state.mission_id != context.mission_id
            or state.trace_id != context.trace_id
        ):
            raise ValueError(
                "Harness state identity conflicts with ExecutionContext"
            )
