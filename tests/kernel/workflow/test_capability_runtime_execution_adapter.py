from typing import Any

from rkjo_kernel.agents.base_agent import BaseAgent
from rkjo_kernel.messages.agent_message import AgentMessage
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
    CapabilityRuntimeExecutionAdapter,
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


class IdentityAgent(BaseAgent):
    def process(
        self,
        message: AgentMessage,
    ) -> Any:
        return {
            "agent_name": self.agent_name,
            "payload": message.payload,
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
            "report_generated": validation["valid"],
            "request_id": validation["request_id"],
        }


def create_service() -> RegistryService:
    return RegistryService(
        AgentRegistry()
    )


def register_runtime(
    *,
    service: RegistryService,
    agent_class,
    agent_name: str,
    queue_name: str,
    capability_name: str,
    priority: int = 5,
    status: AgentStatus = AgentStatus.AVAILABLE,
    confidence_score: float = 1.0,
) -> AgentRuntime:
    event_bus = FakeEventBus()

    service.register_agent(
        AgentDescriptor(
            name=agent_name,
            display_name=agent_name,
            product="RKJO",
            queue_name=queue_name,
            status=status,
            priority=priority,
            capabilities=[
                AgentCapability(
                    name=capability_name,
                    description=capability_name,
                    confidence_score=confidence_score,
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


def test_capability_adapter_selects_best_available_agent():
    service = create_service()

    low_runtime = register_runtime(
        service=service,
        agent_class=IdentityAgent,
        agent_name="rkjo.risk_agent_low",
        queue_name="rkjo.risk.low",
        capability_name="risk.analysis",
        priority=2,
    )

    high_runtime = register_runtime(
        service=service,
        agent_class=IdentityAgent,
        agent_name="rkjo.risk_agent_high",
        queue_name="rkjo.risk.high",
        capability_name="risk.analysis",
        priority=9,
    )

    adapter = CapabilityRuntimeExecutionAdapter(
        discovery=AgentDiscovery(service),
        runtimes={
            "rkjo.risk_agent_low": low_runtime,
            "rkjo.risk_agent_high": high_runtime,
        },
    )

    step = WorkflowStep(
        step_id="risk",
        name="Analyze risk",
        capability_name="risk.analysis",
        position=0,
    )

    result = adapter.execute(
        step=step,
        context=WorkflowContext(
            input_data={
                "temperature": 38,
            },
            metadata={
                "correlation_id": "CORR-001",
            },
        ),
    )

    assert result.success is True
    assert result.output["agent_name"] == (
        "rkjo.risk_agent_high"
    )
    assert result.output["correlation_id"] == (
        "CORR-001"
    )
    assert result.metadata["adapter"] == (
        "capability_runtime"
    )
    assert result.metadata["capability_name"] == (
        "risk.analysis"
    )
    assert result.metadata["selected_agent_name"] == (
        "rkjo.risk_agent_high"
    )
    assert result.metadata["discovery_score"] > 0
    assert low_runtime.total_runtime_messages == 0
    assert high_runtime.total_runtime_messages == 1


def test_capability_adapter_ignores_unavailable_agent():
    service = create_service()

    stopped_runtime = register_runtime(
        service=service,
        agent_class=IdentityAgent,
        agent_name="rkjo.stopped_agent",
        queue_name="rkjo.stopped",
        capability_name="risk.analysis",
        priority=10,
        status=AgentStatus.STOPPED,
    )

    available_runtime = register_runtime(
        service=service,
        agent_class=IdentityAgent,
        agent_name="rkjo.available_agent",
        queue_name="rkjo.available",
        capability_name="risk.analysis",
        priority=3,
    )

    adapter = CapabilityRuntimeExecutionAdapter(
        discovery=AgentDiscovery(service),
        runtimes={
            "rkjo.stopped_agent": stopped_runtime,
            "rkjo.available_agent": available_runtime,
        },
    )

    result = adapter.execute(
        step=WorkflowStep(
            step_id="risk",
            name="Analyze risk",
            capability_name="risk.analysis",
        ),
        context=WorkflowContext(),
    )

    assert result.success is True
    assert result.output["agent_name"] == (
        "rkjo.available_agent"
    )
    assert stopped_runtime.total_runtime_messages == 0
    assert available_runtime.total_runtime_messages == 1


def test_capability_adapter_fails_when_no_agent_exists():
    service = create_service()

    adapter = CapabilityRuntimeExecutionAdapter(
        discovery=AgentDiscovery(service),
        runtimes={},
    )

    result = adapter.execute(
        step=WorkflowStep(
            step_id="risk",
            name="Analyze risk",
            capability_name="risk.analysis",
        ),
        context=WorkflowContext(),
    )

    assert result.success is False
    assert result.error == (
        "No available agent provides capability "
        "'risk.analysis'."
    )


def test_capability_adapter_fails_when_runtime_is_missing():
    service = create_service()

    service.register_agent(
        AgentDescriptor(
            name="rkjo.risk_agent",
            display_name="Risk agent",
            product="RKJO",
            queue_name="rkjo.risk",
            status=AgentStatus.AVAILABLE,
            capabilities=[
                AgentCapability(
                    name="risk.analysis",
                    description="Risk analysis",
                )
            ],
        )
    )

    adapter = CapabilityRuntimeExecutionAdapter(
        discovery=AgentDiscovery(service),
        runtimes={},
    )

    result = adapter.execute(
        step=WorkflowStep(
            step_id="risk",
            name="Analyze risk",
            capability_name="risk.analysis",
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
    assert result.metadata["adapter"] == (
        "capability_runtime"
    )


def test_capability_adapter_rejects_direct_agent_target():
    service = create_service()

    adapter = CapabilityRuntimeExecutionAdapter(
        discovery=AgentDiscovery(service),
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
        "CapabilityRuntimeExecutionAdapter requires "
        "a workflow step targeted by capability_name."
    )
    assert result.metadata["routing_mode"] == "agent"


def test_capability_adapter_converts_discovery_exception():
    class FailingDiscovery:
        def discover(self, criteria):
            raise RuntimeError(
                "Discovery unavailable"
            )

    adapter = CapabilityRuntimeExecutionAdapter(
        discovery=FailingDiscovery(),
        runtimes={},
    )

    result = adapter.execute(
        step=WorkflowStep(
            step_id="risk",
            name="Analyze risk",
            capability_name="risk.analysis",
        ),
        context=WorkflowContext(),
    )

    assert result.success is False
    assert result.error == (
        "Agent discovery failed for capability "
        "'risk.analysis': RuntimeError: "
        "Discovery unavailable"
    )
    assert result.metadata["exception_type"] == (
        "RuntimeError"
    )


def test_capability_adapter_executes_complete_workflow():
    service = create_service()

    validation_runtime = register_runtime(
        service=service,
        agent_class=ValidationAgent,
        agent_name="rkjo.validation_agent",
        queue_name="rkjo.validation",
        capability_name="request.validation",
        priority=8,
    )

    report_runtime = register_runtime(
        service=service,
        agent_class=ReportAgent,
        agent_name="rkjo.report_agent",
        queue_name="rkjo.report",
        capability_name="report.generation",
        priority=8,
    )

    adapter = CapabilityRuntimeExecutionAdapter(
        discovery=AgentDiscovery(service),
        runtimes={
            "rkjo.validation_agent": (
                validation_runtime
            ),
            "rkjo.report_agent": report_runtime,
        },
    )

    definition = WorkflowDefinition(
        workflow_id="dynamic-report",
        name="Dynamic report",
        steps=[
            WorkflowStep(
                step_id="validate",
                name="Validate request",
                capability_name=(
                    "request.validation"
                ),
                position=0,
            ),
            WorkflowStep(
                step_id="report",
                name="Generate report",
                capability_name=(
                    "report.generation"
                ),
                position=1,
            ),
        ],
    )

    engine = WorkflowEngine()

    execution = engine.create_execution(
        definition,
        input_data={
            "request_id": "REQ-900",
        },
        metadata={
            "correlation_id": "CORR-900",
        },
    )

    WorkflowExecutor(
        adapter=adapter,
        engine=engine,
    ).execute(execution)

    assert execution.status == WorkflowStatus.COMPLETED
    assert execution.context.outputs["validate"] == {
        "valid": True,
        "request_id": "REQ-900",
    }
    assert execution.context.outputs["report"] == {
        "report_generated": True,
        "request_id": "REQ-900",
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

    assert validation_runtime.total_runtime_messages == 1
    assert report_runtime.total_runtime_messages == 1
