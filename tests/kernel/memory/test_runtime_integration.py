from __future__ import annotations

from typing import Any

from rkjo_kernel.agents.base_agent import BaseAgent
from rkjo_kernel.memory import (
    ContextEngine,
    InMemoryMemoryStore,
    MissionMemoryService,
)
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.mission.execution_context import ExecutionContext
from rkjo_kernel.registry.descriptor import AgentDescriptor, AgentStatus
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.runtime.agent_runtime import AgentRuntime
from rkjo_kernel.runtime.context_runtime import AgentContextRuntime
from rkjo_kernel.services.registry_service import RegistryService


class FakeEventBus:
    def consume_agent_messages(self, queue_name, callback): pass
    def publish_agent_message(self, queue_name, message): pass
    def publish(self, queue_name, message): pass
    def consume(self, queue_name, callback): pass
    def close(self): pass


class ContextAwareAgent(BaseAgent):
    def process(self, message: AgentMessage) -> Any:
        package = message.metadata.get("context_package")
        return {
            "has_context": package is not None,
            "memory": [item.content for item in package.items] if package else [],
        }


def build_runtime() -> tuple[AgentRuntime, InMemoryMemoryStore]:
    bus = FakeEventBus()
    registry = AgentRegistry()
    service = RegistryService(registry)
    service.register_agent(
        AgentDescriptor(
            name="rkjo.context.agent",
            display_name="Context Agent",
            product="RKJO",
            queue_name="rkjo.context",
            status=AgentStatus.STOPPED,
        )
    )
    agent = ContextAwareAgent(
        agent_name="rkjo.context.agent",
        queue_name="rkjo.context",
        event_bus=bus,
    )
    store = InMemoryMemoryStore()
    runtime = AgentRuntime(
        agent=agent,
        event_bus=bus,
        registry_service=service,
        context_runtime=AgentContextRuntime(ContextEngine(store)),
    )
    return runtime, store


def execution_context() -> ExecutionContext:
    return ExecutionContext(
        mission_id="mission-1",
        trace_id="trace-1",
        tenant_id="tenant-a",
        user_id="user-1",
    )


def message(**metadata) -> AgentMessage:
    base = {
        "mission_id": "mission-1",
        "trace_id": "trace-1",
        "tenant_id": "tenant-a",
        "user_id": "user-1",
    }
    base.update(metadata)
    return AgentMessage(
        source="orchestrator",
        target="rkjo.context.agent",
        payload={"question": "What do we know?"},
        metadata=base,
    )


def test_runtime_injects_mission_memory_before_agent_processing() -> None:
    runtime, store = build_runtime()
    MissionMemoryService(store).remember(
        context=execution_context(),
        content="Mission prefers concise answers.",
        importance=0.9,
    )

    result = runtime.execute(message())

    assert result["has_context"] is True
    assert result["memory"] == ["Mission prefers concise answers."]


def test_runtime_attaches_context_package_to_message() -> None:
    runtime, _ = build_runtime()
    msg = message()

    runtime.execute(msg)

    package = msg.metadata["context_package"]
    assert package.mission_id == "mission-1"
    assert package.tenant_id == "tenant-a"
    assert package.trace_id == "trace-1"


def test_runtime_without_context_runtime_remains_backward_compatible() -> None:
    runtime, _ = build_runtime()
    runtime.context_runtime = None

    result = runtime.execute(message())

    assert result["has_context"] is False


def test_runtime_skips_context_when_mission_metadata_is_missing() -> None:
    runtime, _ = build_runtime()
    msg = message()
    msg.metadata.pop("mission_id")

    result = runtime.execute(msg)

    assert result["has_context"] is False


def test_runtime_skips_context_when_tenant_metadata_is_missing() -> None:
    runtime, _ = build_runtime()
    msg = message()
    msg.metadata.pop("tenant_id")

    result = runtime.execute(msg)

    assert result["has_context"] is False
