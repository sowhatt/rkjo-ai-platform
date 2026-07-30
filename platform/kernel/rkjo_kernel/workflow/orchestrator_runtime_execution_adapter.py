"""Execute workflow steps using Orchestrator dispatch plans."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from rkjo_kernel.orchestrator.orchestrator import (
    AgentOrchestrator,
    MissionRequest,
    NoSuitableAgentError,
)
from rkjo_kernel.runtime.agent_runtime import AgentRuntime
from rkjo_kernel.workflow.agent_execution_adapter import (
    AgentExecutionAdapter,
)
from rkjo_kernel.workflow.execution_result import ExecutionResult
from rkjo_kernel.workflow.models.workflow_context import (
    WorkflowContext,
)
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep


class OrchestratorRuntimeExecutionAdapter(
    AgentExecutionAdapter
):
    """Plan missions through the Orchestrator and execute locally.

    The Orchestrator owns:

    - capability discovery;
    - agent selection;
    - message construction;
    - routing metadata.

    This adapter owns:

    - local runtime lookup;
    - synchronous runtime execution;
    - conversion to ExecutionResult.

    No message is published to the EventBus.
    """

    def __init__(
        self,
        *,
        orchestrator: AgentOrchestrator,
        runtimes: Mapping[str, AgentRuntime],
        product: str = "RKJO",
        source: str = "rkjo.workflow",
        priority: int = 5,
    ) -> None:
        if not product or not product.strip():
            raise ValueError(
                "Orchestrator runtime product must not be empty."
            )

        if not source or not source.strip():
            raise ValueError(
                "Orchestrator runtime source must not be empty."
            )

        if priority < 1 or priority > 10:
            raise ValueError(
                "Orchestrator runtime priority must be "
                "between 1 and 10."
            )

        self.orchestrator = orchestrator
        self._runtimes = dict(runtimes)
        self.product = product.strip()
        self.source = source.strip()
        self.priority = priority

    def execute(
        self,
        *,
        step: WorkflowStep,
        context: WorkflowContext,
    ) -> ExecutionResult:
        """Plan and execute one capability-targeted step."""
        capability_name = step.capability_name

        if capability_name is None:
            return ExecutionResult.failed(
                error=(
                    "OrchestratorRuntimeExecutionAdapter "
                    "requires a workflow step targeted by "
                    "capability_name."
                ),
                metadata={
                    "adapter": "orchestrator_runtime",
                    "routing_mode": step.routing_mode,
                    "agent_name": step.agent_name,
                    "workflow_step_id": step.step_id,
                },
            )

        payload = self._build_payload(context)

        try:
            plan = self.orchestrator.plan(
                MissionRequest(
                    capability_name=capability_name,
                    payload=payload,
                    product=self._metadata_string(
                        step=step,
                        context=context,
                        key="product",
                        default=self.product,
                    ),
                    source=self.source,
                    priority=self._metadata_integer(
                        step=step,
                        context=context,
                        key="priority",
                        default=self.priority,
                    ),
                    region=self._metadata_optional_string(
                        step=step,
                        context=context,
                        key="region",
                    ),
                    language=self._metadata_optional_string(
                        step=step,
                        context=context,
                        key="language",
                    ),
                    max_cost=self._metadata_optional_number(
                        step=step,
                        context=context,
                        key="max_cost",
                    ),
                    max_duration_ms=(
                        self._metadata_optional_integer(
                            step=step,
                            context=context,
                            key="max_duration_ms",
                        )
                    ),
                    correlation_id=(
                        self._correlation_id(context)
                    ),
                    metadata=self._build_message_metadata(
                        step=step,
                        context=context,
                    ),
                )
            )
        except NoSuitableAgentError as exc:
            return ExecutionResult.failed(
                error=str(exc),
                metadata={
                    "adapter": "orchestrator_runtime",
                    "routing_mode": "capability",
                    "capability_name": capability_name,
                    "workflow_step_id": step.step_id,
                },
            )
        except Exception as exc:
            message = (
                str(exc).strip()
                or exc.__class__.__name__
            )

            return ExecutionResult.failed(
                error=(
                    "Orchestrator planning failed for "
                    f"capability '{capability_name}': "
                    f"{exc.__class__.__name__}: {message}"
                ),
                metadata={
                    "adapter": "orchestrator_runtime",
                    "routing_mode": "capability",
                    "capability_name": capability_name,
                    "workflow_step_id": step.step_id,
                    "exception_type": (
                        exc.__class__.__name__
                    ),
                },
            )

        selected_agent = plan.discovery.agent
        runtime = self._runtimes.get(selected_agent.name)

        if runtime is None:
            return ExecutionResult.failed(
                error=(
                    "No local runtime is registered for agent "
                    f"'{selected_agent.name}'."
                ),
                metadata=self._build_result_metadata(
                    step=step,
                    plan=plan,
                ),
            )

        actual_agent_name = runtime.agent.agent_name

        if actual_agent_name != selected_agent.name:
            return ExecutionResult.failed(
                error=(
                    f"Runtime registered as "
                    f"'{selected_agent.name}' contains agent "
                    f"'{actual_agent_name}'."
                ),
                metadata={
                    **self._build_result_metadata(
                        step=step,
                        plan=plan,
                    ),
                    "actual_agent_name": actual_agent_name,
                },
            )

        try:
            output = runtime.execute(plan.message)
        except Exception as exc:
            message = (
                str(exc).strip()
                or exc.__class__.__name__
            )

            return ExecutionResult.failed(
                error=(
                    f"{exc.__class__.__name__}: {message}"
                ),
                duration_ms=runtime.last_duration_ms,
                metadata={
                    **self._build_result_metadata(
                        step=step,
                        plan=plan,
                    ),
                    "runtime_status": runtime.status.value,
                    "exception_type": (
                        exc.__class__.__name__
                    ),
                },
            )

        return ExecutionResult.succeeded(
            output=output,
            duration_ms=runtime.last_duration_ms,
            metadata={
                **self._build_result_metadata(
                    step=step,
                    plan=plan,
                ),
                "runtime_status": runtime.status.value,
            },
        )

    def register_runtime(
        self,
        runtime: AgentRuntime,
    ) -> None:
        """Register or replace a local runtime."""
        self._runtimes[
            runtime.agent.agent_name
        ] = runtime

    def unregister_runtime(
        self,
        agent_name: str,
    ) -> AgentRuntime | None:
        """Remove and return a local runtime."""
        return self._runtimes.pop(
            agent_name,
            None,
        )

    def get_runtime(
        self,
        agent_name: str,
    ) -> AgentRuntime | None:
        """Return a local runtime by agent name."""
        return self._runtimes.get(agent_name)

    @staticmethod
    def _build_payload(
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Build the mission payload from workflow context."""
        payload = deepcopy(context.input_data)
        payload.update(deepcopy(context.variables))

        if context.outputs:
            payload["workflow_outputs"] = deepcopy(
                context.outputs
            )

        return payload

    @staticmethod
    def _build_message_metadata(
        *,
        step: WorkflowStep,
        context: WorkflowContext,
    ) -> dict[str, Any]:
        """Build trace metadata sent inside the mission."""
        return {
            **deepcopy(context.metadata),
            **deepcopy(step.metadata),
            "workflow_step_id": step.step_id,
            "workflow_step_name": step.name,
            "execution_adapter": (
                "orchestrator_runtime"
            ),
        }

    @staticmethod
    def _correlation_id(
        context: WorkflowContext,
    ) -> str:
        """Return an existing correlation ID when available."""
        value = context.metadata.get(
            "correlation_id"
        )

        if isinstance(value, str) and value.strip():
            return value.strip()

        from uuid import uuid4

        return str(uuid4())

    @staticmethod
    def _metadata_value(
        *,
        step: WorkflowStep,
        context: WorkflowContext,
        key: str,
        default: Any = None,
    ) -> Any:
        """Resolve step metadata before context metadata."""
        if key in step.metadata:
            return step.metadata[key]

        return context.metadata.get(key, default)

    @classmethod
    def _metadata_string(
        cls,
        *,
        step: WorkflowStep,
        context: WorkflowContext,
        key: str,
        default: str,
    ) -> str:
        value = cls._metadata_value(
            step=step,
            context=context,
            key=key,
            default=default,
        )

        if not isinstance(value, str) or not value.strip():
            return default

        return value.strip()

    @classmethod
    def _metadata_optional_string(
        cls,
        *,
        step: WorkflowStep,
        context: WorkflowContext,
        key: str,
    ) -> str | None:
        value = cls._metadata_value(
            step=step,
            context=context,
            key=key,
        )

        if not isinstance(value, str) or not value.strip():
            return None

        return value.strip()

    @classmethod
    def _metadata_integer(
        cls,
        *,
        step: WorkflowStep,
        context: WorkflowContext,
        key: str,
        default: int,
    ) -> int:
        value = cls._metadata_value(
            step=step,
            context=context,
            key=key,
            default=default,
        )

        if isinstance(value, bool) or not isinstance(value, int):
            return default

        return value

    @classmethod
    def _metadata_optional_integer(
        cls,
        *,
        step: WorkflowStep,
        context: WorkflowContext,
        key: str,
    ) -> int | None:
        value = cls._metadata_value(
            step=step,
            context=context,
            key=key,
        )

        if isinstance(value, bool) or not isinstance(value, int):
            return None

        return value

    @classmethod
    def _metadata_optional_number(
        cls,
        *,
        step: WorkflowStep,
        context: WorkflowContext,
        key: str,
    ) -> float | None:
        value = cls._metadata_value(
            step=step,
            context=context,
            key=key,
        )

        if isinstance(value, bool):
            return None

        if not isinstance(value, (int, float)):
            return None

        return float(value)

    @staticmethod
    def _build_result_metadata(
        *,
        step: WorkflowStep,
        plan: Any,
    ) -> dict[str, Any]:
        """Build routing and trace metadata."""
        selected_agent = plan.discovery.agent

        return {
            "adapter": "orchestrator_runtime",
            "routing_mode": "capability",
            "capability_name": step.capability_name,
            "selected_agent_name": selected_agent.name,
            "selected_agent_version": (
                selected_agent.version
            ),
            "selected_capability_version": (
                plan.discovery.capability.version
            ),
            "discovery_score": plan.discovery.score,
            "queue_name": plan.queue_name,
            "workflow_step_id": step.step_id,
            "message_id": plan.message.message_id,
            "correlation_id": (
                plan.message.correlation_id
            ),
        }
