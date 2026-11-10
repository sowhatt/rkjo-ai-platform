from typing import Any

import pytest

from rkjo_kernel.agents.base_agent import BaseAgent
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.mission import ExecutionContext
from rkjo_kernel.registry.descriptor import AgentDescriptor, AgentStatus
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.runtime.agent_runtime import AgentRuntime
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.workflow import (
    WorkflowContext,
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowStep,
)
from rkjo_kernel.workflow.async_dispatch import AsyncWorkflowDispatcher


class RecordingEventBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, AgentMessage]] = []

    def publish_agent_message(self, *, queue_name, message) -> None:
        self.published.append((queue_name, message))

    def consume_agent_messages(self, queue_name, callback) -> None:
        self.callback = callback

    def close(self) -> None:
        pass


class CapturingAgent(BaseAgent):
    def __init__(self, *, event_bus) -> None:
        super().__init__(
            agent_name="education.tutor",
            queue_name="education.tutor",
            event_bus=event_bus,
        )
        self.received_metadata: dict[str, Any] | None = None

    def process(self, message: AgentMessage) -> Any:
        self.received_metadata = dict(message.metadata)
        return {"ok": True}


def make_execution() -> WorkflowExecution:
    definition = WorkflowDefinition(
        workflow_id="education.trace.test",
        name="Trace propagation",
        steps=[
            WorkflowStep(
                step_id="teach",
                name="Teach",
                capability_name="education.explain",
                position=0,
            )
        ],
    )
    return WorkflowExecution(
        definition=definition,
        execution_id="workflow-exec-1",
        context=WorkflowContext(
            input_data={"topic": "fractions"},
            metadata={"existing_key": "kept"},
        ),
    )


def test_workflow_binding_propagates_mission_and_trace_to_agent_message():
    execution = make_execution()
    context = ExecutionContext(
        mission_id="mission-1",
        trace_id="trace-1",
        tenant_id="tenant-1",
        user_id="user-1",
        correlation_id="corr-1",
    )

    bound = execution.bind_execution_context(context)

    event_bus = RecordingEventBus()
    dispatcher = AsyncWorkflowDispatcher(event_bus=event_bus)

    step = execution.definition.steps[0]
    _, message = dispatcher.prepare(
        step=step,
        context=execution.context,
        queue_name="education.tutor",
        execution_id=execution.execution_id,
        correlation_id=bound.correlation_id,
        reply_queue="rkjo.workflow.results",
        target_agent_name="education.tutor",
    )

    assert bound.workflow_execution_id == "workflow-exec-1"
    assert execution.metadata["mission_id"] == "mission-1"
    assert execution.context.metadata["trace_id"] == "trace-1"
    assert execution.context.metadata["existing_key"] == "kept"

    assert message.metadata["mission_id"] == "mission-1"
    assert message.metadata["trace_id"] == "trace-1"
    assert message.metadata["workflow_execution_id"] == "workflow-exec-1"
    assert message.metadata["workflow_step_id"] == "teach"
    assert message.metadata["capability_name"] == "education.explain"
    assert message.metadata["tenant_id"] == "tenant-1"
    assert message.metadata["user_id"] == "user-1"
    assert message.correlation_id == "corr-1"


def test_agent_runtime_receives_same_mission_and_trace_metadata():
    execution = make_execution()
    execution.bind_execution_context(
        ExecutionContext(
            mission_id="mission-runtime",
            trace_id="trace-runtime",
        )
    )

    event_bus = RecordingEventBus()
    dispatcher = AsyncWorkflowDispatcher(event_bus=event_bus)
    step = execution.definition.steps[0]
    _, message = dispatcher.prepare(
        step=step,
        context=execution.context,
        queue_name="education.tutor",
        execution_id=execution.execution_id,
        target_agent_name="education.tutor",
    )

    registry = AgentRegistry()
    service = RegistryService(registry)
    service.register_agent(
        AgentDescriptor(
            name="education.tutor",
            display_name="Education Tutor",
            product="Education",
            queue_name="education.tutor",
            status=AgentStatus.STOPPED,
        )
    )
    agent = CapturingAgent(event_bus=event_bus)
    runtime = AgentRuntime(
        agent=agent,
        event_bus=event_bus,
        registry_service=service,
    )

    result = runtime.execute(message)

    assert result == {"ok": True}
    assert agent.received_metadata is not None
    assert agent.received_metadata["mission_id"] == "mission-runtime"
    assert agent.received_metadata["trace_id"] == "trace-runtime"
    assert agent.received_metadata["workflow_execution_id"] == "workflow-exec-1"
    assert agent.received_metadata["workflow_step_id"] == "teach"
    assert agent.received_metadata["capability_name"] == "education.explain"


def test_binding_rejects_context_for_another_workflow_execution():
    execution = make_execution()
    foreign_context = ExecutionContext(
        mission_id="mission-1",
        workflow_execution_id="another-execution",
    )

    with pytest.raises(ValueError, match="does not match"):
        execution.bind_execution_context(foreign_context)
