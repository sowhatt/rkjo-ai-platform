"""Library boundaries complement (and never replace) the real-process recipe."""
from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.registry.descriptor import AgentDescriptor, AgentStatus
from rkjo_kernel.registry.discovery import AgentDiscovery
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.tools.descriptor import ToolDescriptor
from rkjo_kernel.tools.invoker import ToolInvoker
from rkjo_kernel.tools.registry import ToolRegistry
from rkjo_kernel.tools.resolver import CapabilityToolResolver
from rkjo_kernel.workflow.capability_tool_execution_adapter import CapabilityToolExecutionAdapter
from rkjo_kernel.workflow.models.workflow_context import WorkflowContext
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep


def test_tool_boundary_preserves_server_identity_over_step_metadata():
    registry = RegistryService(AgentRegistry())
    registry.register_agent(AgentDescriptor(
        name="neutral.agent", display_name="Neutral", product="RKJO", queue_name="neutral",
        status=AgentStatus.AVAILABLE, capabilities=[AgentCapability(
            name="neutral.echo", description="Local neutral echo", tools=["neutral.echo"])]))
    tools = ToolRegistry()
    tools.register(ToolDescriptor(name="neutral.echo", display_name="Echo", description="Echo"),
                   handler=lambda payload, context: context.model_dump())
    adapter = CapabilityToolExecutionAdapter(discovery=AgentDiscovery(registry),
        resolver=CapabilityToolResolver(tools), invoker=ToolInvoker(tools))
    canonical = {"tenant_id": "tenant-a", "user_id": "alice", "mission_id": "Mission-A",
                 "trace_id": "Trace-A", "request_id": "Request-A",
                 "policy_context": {"api_role": "operator"}}
    result = adapter.execute(
        step=WorkflowStep(step_id="echo", name="Echo", capability_name="neutral.echo",
                          metadata={"user_id": "mallory", "policy_context": {"api_role": "admin"}}),
        context=WorkflowContext(metadata=canonical))
    assert result.success
    assert result.output["metadata"] == canonical
    assert result.output["tenant_id"] == "tenant-a"
    assert result.output["mission_id"] == "Mission-A"
    assert result.output["trace_id"] == "Trace-A"
