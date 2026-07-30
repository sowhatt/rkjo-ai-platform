from typing import Any

from rkjo_kernel.agents.base_agent import BaseAgent
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.orchestrator.orchestrator import (
    AgentOrchestrator,
)
from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.registry.discovery import AgentDiscovery
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.runtime.agent_runtime import AgentRuntime
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.workflow import (
    OrchestratorRuntimeExecutionAdapter,
    WorkflowContext,
    WorkflowDefinition,
    WorkflowEngine,
    WorkflowExecutor,
    WorkflowStatus,
    WorkflowStep,
)


class FakeEventBus:
    def __init__(self) -> None:
        self.published_messages = []

    def publish_agent_message(
        self,
        queue_name: str,
        message: AgentMessage,
    ) -> None:
        self.published_messages.append(
            (queue_name, message)
        )

    def consume_agent_messages(
        self,
        queue_name: str,
        callback,
    ) -> None:
        self.queue_name = queue_name
        self.callback = callback

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

    def close(self) -> None:
        pass


class IdentityAgent(BaseAgent):
    def process(
        self,
        message: AgentMessage,
    ) -> Any:
        return {
            "agent_name": self.agent_name,
            "payload": message.payload,
            "metadata": message.metadata,
            "correlation_id": message.correlation_id,
        }


class ValidationAgent(BaseAgent):
    def process(
        self,
        message: AgentMessage,
    ) -> Any:
        return {
            "valid": True,
            "request_id": message.payload[
                "request_id"
            ],
        }


class ReportAgent(BaseAgent):
    def process(
        self,
        message: AgentMessage,
    ) -> Any:
        validation = message.payload[
            "workflow_outputs"
        ]["validate"]

        return {
            "generated": validation["valid"],
            "request_id": validation["request_id"],
        }


def create_environment():
    service = RegistryService(
        AgentRegistry()
    )
    event_bus = FakeEventBus()
    orchestrator = AgentOrchestrator(
        discovery=AgentDiscovery(service),
        event_bus=event_bus,
    )

    return service, event_bus, orchestrator


def register_runtime(
    *,
    service: RegistryService,
    event_bus: FakeEventBus,
    agent_class,
    agent_name: str,
    capability_name: str,
    priority: int = 5,
    status: AgentStatus = AgentStatus.AVAILABLE,
    regions: list[str] | None = None,
) -> AgentRuntime:
    queue_name = f"{agent_name}.queue"

    service.register_agent(
        AgentDescriptor(
            name=agent_name,
            display_name=agent_name,
            product="RKJO",
            queue_name=queue_name,
            status=status,
            priority=priority,
            supported_regions=regions or [],
            capabilities=[
                AgentCapability(
                    name=capability_name,
                    description=capability_name,
                )
            ],
        )
    )

    agent = agent_class(
        agent_name=agent_name,
        queue_name=queue_name,
        event_bus=event_bus,
    )

    return AgentRuntime(
        agent=agent,
        event_bus=event_bus,
        registry_service=service,
    )


def test_adapter_uses_orchestrator_plan_without_publishing():
    service, event_bus, orchestrator = create_environment()

    runtime = register_runtime(
        service=service,
        event_bus=event_bus,
        agent_class=IdentityAgent,
        agent_name="rkjo.risk_agent",
        capability_name="risk_analysis",
        priority=9,
    )

    adapter = OrchestratorRuntimeExecutionAdapter(
        orchestrator=orchestrator,
        runtimes={
            "rkjo.risk_agent": runtime,
        },
        product="ADIP",
    )

    result = adapter.execute(
        step=WorkflowStep(
            step_id="risk",
            name="Analyze risk",
            capability_name="risk_analysis",
        ),
        context=WorkflowContext(
            input_data={
                "temperature": 39,
            },
            variables={
                "crop": "maize",
            },
            metadata={
                "correlation_id": "CORR-001",
            },
        ),
    )

    assert result.success is True
    assert result.output["agent_name"] == (
        "rkjo.risk_agent"
    )
    assert result.output["payload"] == {
        "temperature": 39,
        "crop": "maize",
    }
    assert result.output["correlation_id"] == (
        "CORR-001"
    )
    assert result.metadata["adapter"] == (
        "orchestrator_runtime"
    )
    assert result.metadata["selected_agent_name"] == (
        "rkjo.risk_agent"
    )
    assert event_bus.published_messages == []
    assert runtime.total_runtime_messages == 1


def test_adapter_passes_discovery_filters_from_metadata():
    service, event_bus, orchestrator = create_environment()

    france_runtime = register_runtime(
        service=service,
        event_bus=event_bus,
        agent_class=IdentityAgent,
        agent_name="rkjo.france_agent",
        capability_name="risk_analysis",
        priority=5,
        regions=["france"],
    )

    canada_runtime = register_runtime(
        service=service,
        event_bus=event_bus,
        agent_class=IdentityAgent,
        agent_name="rkjo.canada_agent",
        capability_name="risk_analysis",
        priority=10,
        regions=["canada"],
    )

    adapter = OrchestratorRuntimeExecutionAdapter(
        orchestrator=orchestrator,
        runtimes={
            "rkjo.france_agent": france_runtime,
            "rkjo.canada_agent": canada_runtime,
        },
    )

    result = adapter.execute(
        step=WorkflowStep(
            step_id="risk",
            name="Analyze risk",
            capability_name="risk_analysis",
            metadata={
                "region": "france",
            },
        ),
        context=WorkflowContext(),
    )

    assert result.success is True
    assert result.metadata["selected_agent_name"] == (
        "rkjo.france_agent"
    )
    assert france_runtime.total_runtime_messages == 1
    assert canada_runtime.total_runtime_messages == 0


def test_adapter_fails_when_no_agent_matches():
    _, event_bus, orchestrator = create_environment()

    adapter = OrchestratorRuntimeExecutionAdapter(
        orchestrator=orchestrator,
        runtimes={},
    )

    result = adapter.execute(
        step=WorkflowStep(
            step_id="risk",
            name="Analyze risk",
            capability_name="unknown_capability",
        ),
        context=WorkflowContext(),
    )

    assert result.success is False
    assert result.error == (
        "No available agent matches capability "
        "'unknown_capability'."
    )
    assert event_bus.published_messages == []


def test_adapter_fails_when_selected_runtime_is_missing():
    service, event_bus, orchestrator = create_environment()

    service.register_agent(
        AgentDescriptor(
            name="rkjo.risk_agent",
            display_name="Risk agent",
            product="RKJO",
            queue_name="rkjo.risk.queue",
            status=AgentStatus.AVAILABLE,
            capabilities=[
                AgentCapability(
                    name="risk_analysis",
                    description="Risk analysis",
                )
            ],
        )
    )

    adapter = OrchestratorRuntimeExecutionAdapter(
        orchestrator=orchestrator,
        runtimes={},
    )

    result = adapter.execute(
        step=WorkflowStep(
            step_id="risk",
            name="Analyze risk",
            capability_name="risk_analysis",
        ),
        context=WorkflowContext(),
    )

    assert result.success is False
    assert result.error == (
        "No local runtime is registered for agent "
        "'rkjo.risk_agent'."
    )
    assert result.metadata["selected_agent_name"] == (
        "rkjo.risk_agent"
    )
    assert event_bus.published_messages == []


def test_adapter_rejects_direct_agent_target():
    _, _, orchestrator = create_environment()

    adapter = OrchestratorRuntimeExecutionAdapter(
        orchestrator=orchestrator,
        runtimes={},
    )

    result = adapter.execute(
        step=WorkflowStep(
            step_id="risk",
            name="Analyze risk",
            agent_name="rkjo.risk_agent",
        ),
        context=WorkflowContext(),
    )

    assert result.success is False
    assert result.error == (
        "OrchestratorRuntimeExecutionAdapter "
        "requires a workflow step targeted by "
        "capability_name."
    )


def test_adapter_executes_complete_dynamic_workflow():
    service, event_bus, orchestrator = create_environment()

    validation_runtime = register_runtime(
        service=service,
        event_bus=event_bus,
        agent_class=ValidationAgent,
        agent_name="rkjo.validation_agent",
        capability_name="request_validation",
        priority=8,
    )

    report_runtime = register_runtime(
        service=service,
        event_bus=event_bus,
        agent_class=ReportAgent,
        agent_name="rkjo.report_agent",
        capability_name="report_generation",
        priority=8,
    )

    adapter = OrchestratorRuntimeExecutionAdapter(
        orchestrator=orchestrator,
        runtimes={
            "rkjo.validation_agent": (
                validation_runtime
            ),
            "rkjo.report_agent": report_runtime,
        },
    )

    definition = WorkflowDefinition(
        workflow_id="orchestrated-report",
        name="Orchestrated report",
        steps=[
            WorkflowStep(
                step_id="validate",
                name="Validate request",
                capability_name=(
                    "request_validation"
                ),
                position=0,
            ),
            WorkflowStep(
                step_id="report",
                name="Generate report",
                capability_name=(
                    "report_generation"
                ),
                position=1,
            ),
        ],
    )

    engine = WorkflowEngine()

    execution = engine.create_execution(
        definition,
        input_data={
            "request_id": "REQ-1000",
        },
        metadata={
            "correlation_id": "CORR-1000",
        },
    )

    WorkflowExecutor(
        adapter=adapter,
        engine=engine,
    ).execute(execution)

    assert execution.status == WorkflowStatus.COMPLETED
    assert execution.context.outputs["validate"] == {
        "valid": True,
        "request_id": "REQ-1000",
    }
    assert execution.context.outputs["report"] == {
        "generated": True,
        "request_id": "REQ-1000",
    }

    step_results = execution.context.metadata[
        "step_results"
    ]

    assert step_results["validate"]["metadata"][
        "selected_agent_name"
    ] == "rkjo.validation_agent"

    assert step_results["report"]["metadata"][
        "selected_agent_name"
    ] == "rkjo.report_agent"

    assert event_bus.published_messages == []
    assert validation_runtime.total_runtime_messages == 1
    assert report_runtime.total_runtime_messages == 1
