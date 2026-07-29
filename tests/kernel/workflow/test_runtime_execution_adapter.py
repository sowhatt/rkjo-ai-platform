from typing import Any

import pytest

from rkjo_kernel.agents.base_agent import BaseAgent
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.runtime.agent_runtime import AgentRuntime
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.workflow import (
    RuntimeExecutionAdapter,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowEngine,
    WorkflowExecutor,
    WorkflowStatus,
    WorkflowStep,
)


class FakeEventBus:
    def publish(
        self,
        queue_name: str,
        message: str,
    ) -> None:
        raise NotImplementedError

    def consume(
        self,
        queue_name: str,
        callback,
    ) -> None:
        raise NotImplementedError

    def publish_agent_message(
        self,
        queue_name: str,
        message: AgentMessage,
    ) -> None:
        raise NotImplementedError

    def consume_agent_messages(
        self,
        queue_name: str,
        callback,
    ) -> None:
        self.queue_name = queue_name
        self.callback = callback

    def close(self) -> None:
        pass


class EchoAgent(BaseAgent):
    def process(
        self,
        message: AgentMessage,
    ) -> Any:
        return {
            "payload": message.payload,
            "message_id": message.message_id,
            "correlation_id": message.correlation_id,
        }


class FailingAgent(BaseAgent):
    def process(
        self,
        message: AgentMessage,
    ) -> Any:
        raise RuntimeError(
            "Local agent execution failed"
        )


class ValidationAgent(BaseAgent):
    def process(
        self,
        message: AgentMessage,
    ) -> Any:
        return {
            "validated_request_id": (
                message.payload["request_id"]
            ),
            "valid": True,
        }


class ExecutionAgent(BaseAgent):
    def process(
        self,
        message: AgentMessage,
    ) -> Any:
        validation_output = message.payload[
            "workflow_outputs"
        ]["validate"]

        return {
            "executed": validation_output["valid"],
            "request_id": validation_output[
                "validated_request_id"
            ],
        }


def create_runtime(
    *,
    agent_class,
    agent_name: str,
    queue_name: str,
) -> tuple[RegistryService, AgentRuntime]:
    registry = AgentRegistry()
    service = RegistryService(registry)
    event_bus = FakeEventBus()

    service.register_agent(
        AgentDescriptor(
            name=agent_name,
            display_name=agent_name,
            product="RKJO",
            queue_name=queue_name,
            status=AgentStatus.STOPPED,
        )
    )

    agent = agent_class(
        agent_name=agent_name,
        queue_name=queue_name,
        event_bus=event_bus,
    )

    runtime = AgentRuntime(
        agent=agent,
        event_bus=event_bus,
        registry_service=service,
    )

    return service, runtime


def create_step(
    agent_name: str = "rkjo.echo_agent",
) -> WorkflowStep:
    return WorkflowStep(
        step_id="echo",
        name="Echo input",
        agent_name=agent_name,
        position=0,
    )


def test_runtime_adapter_executes_local_agent():
    _, runtime = create_runtime(
        agent_class=EchoAgent,
        agent_name="rkjo.echo_agent",
        queue_name="rkjo.echo",
    )

    adapter = RuntimeExecutionAdapter(
        runtimes={
            "rkjo.echo_agent": runtime,
        }
    )

    context = WorkflowContext(
        input_data={
            "request_id": "REQ-001",
        },
        variables={
            "mode": "fast",
        },
        outputs={
            "previous": {
                "processed": True,
            },
        },
        metadata={
            "correlation_id": "CORR-001",
        },
    )

    result = adapter.execute(
        step=create_step(),
        context=context,
    )

    assert result.success is True
    assert result.output["payload"] == {
        "request_id": "REQ-001",
        "mode": "fast",
        "workflow_outputs": {
            "previous": {
                "processed": True,
            },
        },
    }
    assert result.output["correlation_id"] == (
        "CORR-001"
    )
    assert result.metadata["agent_name"] == (
        "rkjo.echo_agent"
    )
    assert result.metadata["workflow_step_id"] == (
        "echo"
    )
    assert runtime.total_runtime_messages == 1
    assert runtime.last_duration_ms is not None


def test_runtime_adapter_fails_when_runtime_is_missing():
    adapter = RuntimeExecutionAdapter(
        runtimes={}
    )

    result = adapter.execute(
        step=create_step(),
        context=WorkflowContext(),
    )

    assert result.success is False
    assert result.error == (
        "No local runtime is registered for agent "
        "'rkjo.echo_agent'."
    )


def test_runtime_adapter_detects_mismatched_agent():
    _, runtime = create_runtime(
        agent_class=EchoAgent,
        agent_name="rkjo.actual_agent",
        queue_name="rkjo.actual",
    )

    adapter = RuntimeExecutionAdapter(
        runtimes={
            "rkjo.expected_agent": runtime,
        }
    )

    result = adapter.execute(
        step=create_step(
            agent_name="rkjo.expected_agent"
        ),
        context=WorkflowContext(),
    )

    assert result.success is False
    assert result.error == (
        "Runtime registered as 'rkjo.expected_agent' "
        "contains agent 'rkjo.actual_agent'."
    )


def test_runtime_adapter_converts_agent_exception():
    service, runtime = create_runtime(
        agent_class=FailingAgent,
        agent_name="rkjo.failing_agent",
        queue_name="rkjo.failing",
    )

    adapter = RuntimeExecutionAdapter(
        runtimes={
            "rkjo.failing_agent": runtime,
        }
    )

    result = adapter.execute(
        step=create_step(
            agent_name="rkjo.failing_agent"
        ),
        context=WorkflowContext(),
    )

    assert result.success is False
    assert result.error == (
        "RuntimeError: "
        "Local agent execution failed"
    )
    assert result.metadata["exception_type"] == (
        "RuntimeError"
    )
    assert runtime.last_error == (
        "Local agent execution failed"
    )

    descriptor = service.get_agent(
        "rkjo.failing_agent"
    )

    assert descriptor is not None
    assert descriptor.status == AgentStatus.ERROR


def test_runtime_adapter_validates_priority():
    with pytest.raises(
        ValueError,
        match="between 1 and 10",
    ):
        RuntimeExecutionAdapter(
            runtimes={},
            priority=11,
        )


def test_workflow_executor_runs_real_local_agents():
    _, validation_runtime = create_runtime(
        agent_class=ValidationAgent,
        agent_name="rkjo.validation_agent",
        queue_name="rkjo.validation",
    )

    _, execution_runtime = create_runtime(
        agent_class=ExecutionAgent,
        agent_name="rkjo.execution_agent",
        queue_name="rkjo.execution",
    )

    adapter = RuntimeExecutionAdapter(
        runtimes={
            "rkjo.validation_agent": (
                validation_runtime
            ),
            "rkjo.execution_agent": (
                execution_runtime
            ),
        }
    )

    engine = WorkflowEngine()
    executor = WorkflowExecutor(
        adapter=adapter,
        engine=engine,
    )

    definition = WorkflowDefinition(
        workflow_id="local.runtime.workflow",
        name="Local runtime workflow",
        steps=[
            WorkflowStep(
                step_id="validate",
                name="Validate request",
                agent_name=(
                    "rkjo.validation_agent"
                ),
                position=0,
            ),
            WorkflowStep(
                step_id="execute",
                name="Execute request",
                agent_name=(
                    "rkjo.execution_agent"
                ),
                position=1,
            ),
        ],
    )

    execution = engine.create_execution(
        definition,
        input_data={
            "request_id": "REQ-900",
        },
        metadata={
            "correlation_id": "CORR-900",
        },
    )

    executor.execute(execution)

    assert execution.status == (
        WorkflowStatus.COMPLETED
    )
    assert execution.context.outputs[
        "validate"
    ] == {
        "validated_request_id": "REQ-900",
        "valid": True,
    }
    assert execution.context.outputs[
        "execute"
    ] == {
        "executed": True,
        "request_id": "REQ-900",
    }
    assert (
        validation_runtime.total_runtime_messages
        == 1
    )
    assert (
        execution_runtime.total_runtime_messages
        == 1
    )

def test_runtime_adapter_rejects_capability_target():
    adapter = RuntimeExecutionAdapter(
        runtimes={}
    )

    step = WorkflowStep(
        step_id="risk",
        name="Analyze risk",
        capability_name="risk.analysis",
        position=0,
    )

    result = adapter.execute(
        step=step,
        context=WorkflowContext(),
    )

    assert result.success is False
    assert result.error == (
        "RuntimeExecutionAdapter requires a "
        "workflow step targeted by agent_name. "
        "Capability 'risk.analysis' must be "
        "resolved before local execution."
    )
    assert result.metadata["capability_name"] == (
        "risk.analysis"
    )
    assert result.metadata["workflow_step_id"] == "risk"
