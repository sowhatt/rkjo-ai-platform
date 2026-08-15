import pytest

from rkjo_kernel.agents.base_agent import BaseAgent
from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.monitoring.metrics import MetricsRegistry
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.runtime.agent_runtime import AgentRuntime
from rkjo_kernel.runtime.dead_letter_publisher import (
    DeadLetterPublisher,
)
from rkjo_kernel.runtime.retry_policy import RetryPolicy
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.workflow.async_dispatch import AsyncWorkflowDispatcher
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.models.workflow_context import WorkflowContext
from rkjo_kernel.workflow.models.workflow_definition import (
    WorkflowDefinition,
)
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep
from rkjo_kernel.workflow.repository.memory import (
    InMemoryWorkflowRepository,
)


class FakeEventBus(EventBus):
    def __init__(self):
        self.messages = []

    def publish(self, queue_name, message):
        pass

    def consume(self, queue_name, callback):
        pass

    def publish_agent_message(
        self,
        queue_name,
        message,
    ):
        self.messages.append(
            (queue_name, message)
        )

    def consume_agent_messages(
        self,
        queue_name,
        callback,
    ):
        pass

    def close(self):
        pass


class SuccessAgent(BaseAgent):
    def process(self, message):
        return {"ok": True}


class TimeoutAgent(BaseAgent):
    def process(self, message):
        raise TimeoutError("timeout")


def make_registry(agent_name):
    registry = AgentRegistry()

    service = RegistryService(
        registry=registry
    )

    service.register_agent(
        AgentDescriptor(
            name=agent_name,
            display_name="Metrics Agent",
            product="ADIP",
            queue_name="metrics.queue",
            status=AgentStatus.AVAILABLE,
        )
    )

    return service


def make_definition():
    return WorkflowDefinition(
        workflow_id="metrics-workflow",
        name="Metrics Workflow",
        steps=[
            WorkflowStep(
                step_id="weather",
                name="Weather",
                agent_name="metrics.agent",
            )
        ],
    )


def test_workflow_engine_records_lifecycle_metrics():
    metrics = MetricsRegistry()

    engine = WorkflowEngine(
        repository=InMemoryWorkflowRepository(),
        metrics=metrics,
    )

    execution = engine.create_execution(
        make_definition(),
        execution_id="metrics-exec",
    )

    engine.start(execution)
    engine.start_next_step(execution)
    engine.complete_current_step(execution)
    engine.complete(execution)

    assert metrics.get(
        "workflow.created"
    ) == 1

    assert metrics.get(
        "workflow.started"
    ) == 1

    assert metrics.get(
        "workflow.completed"
    ) == 1


def test_workflow_failure_records_metric():
    metrics = MetricsRegistry()

    engine = WorkflowEngine(
        repository=InMemoryWorkflowRepository(),
        metrics=metrics,
    )

    execution = engine.create_execution(
        make_definition()
    )

    engine.start(execution)
    engine.start_next_step(execution)

    engine.fail_current_step(
        execution,
        error="boom",
    )

    assert metrics.get(
        "workflow.failed"
    ) == 1


def test_dispatch_records_metric():
    metrics = MetricsRegistry()
    bus = FakeEventBus()

    dispatcher = AsyncWorkflowDispatcher(
        event_bus=bus,
        metrics=metrics,
    )

    dispatcher.dispatch(
        step=WorkflowStep(
            step_id="weather",
            name="Weather",
            agent_name="metrics.agent",
        ),
        context=WorkflowContext(),
        queue_name="metrics.queue",
        execution_id="exec-001",
    )

    assert metrics.get(
        "workflow.dispatched"
    ) == 1


def test_runtime_success_records_metric():
    metrics = MetricsRegistry()
    bus = FakeEventBus()

    agent = SuccessAgent(
        agent_name="metrics.agent",
        queue_name="metrics.queue",
        event_bus=bus,
    )

    runtime = AgentRuntime(
        agent=agent,
        event_bus=bus,
        registry_service=make_registry(
            agent.agent_name
        ),
        metrics=metrics,
    )

    runtime.execute(
        AgentMessage(
            source="test",
            target=agent.agent_name,
            payload={},
        )
    )

    assert metrics.get(
        "runtime.success"
    ) == 1


def test_runtime_failure_and_retry_record_metrics():
    metrics = MetricsRegistry()
    bus = FakeEventBus()

    agent = TimeoutAgent(
        agent_name="metrics.agent",
        queue_name="metrics.queue",
        event_bus=bus,
    )

    runtime = AgentRuntime(
        agent=agent,
        event_bus=bus,
        registry_service=make_registry(
            agent.agent_name
        ),
        retry_policy=RetryPolicy(
            max_attempts=3,
            base_delay_seconds=0,
        ),
        metrics=metrics,
    )

    message = AgentMessage(
        source="test",
        target=agent.agent_name,
        payload={},
        metadata={
            "attempt": 1,
        },
    )

    runtime._consume_message(
        message
    )

    assert metrics.get(
        "runtime.failure"
    ) == 1

    assert metrics.get(
        "runtime.retry"
    ) == 1


def test_dead_letter_records_metric():
    metrics = MetricsRegistry()
    bus = FakeEventBus()

    publisher = DeadLetterPublisher(
        event_bus=bus,
        queue_name="metrics.dlq",
        metrics=metrics,
    )

    publisher.publish(
        original_message=AgentMessage(
            source="test",
            target="metrics.agent",
            payload={},
        ),
        reason="permanent_error",
    )

    assert metrics.get(
        "runtime.dead_letter"
    ) == 1


def test_components_remain_compatible_without_metrics():
    engine = WorkflowEngine(
        repository=InMemoryWorkflowRepository()
    )

    execution = engine.create_execution(
        make_definition()
    )

    assert execution is not None
