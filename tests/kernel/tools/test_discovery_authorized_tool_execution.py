from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.registry.descriptor import AgentDescriptor, AgentStatus
from rkjo_kernel.registry.discovery import AgentDiscovery, DiscoveryCriteria
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.tools.context import ToolExecutionContext
from rkjo_kernel.tools.descriptor import ToolDescriptor
from rkjo_kernel.tools.invoker import ToolInvoker
from rkjo_kernel.tools.registry import ToolRegistry
from rkjo_kernel.tools.resolver import CapabilityToolResolver


def test_discovery_resolver_policy_and_invoker_execute_declared_tool():
    agent_registry = AgentRegistry()
    registry_service = RegistryService(agent_registry)

    capability = AgentCapability(
        name="course_search",
        description="Search education courses.",
        tools=["education.search_course"],
    )

    registry_service.register_agent(
        AgentDescriptor(
            name="education.agent",
            display_name="Education Agent",
            product="education",
            queue_name="education.agent",
            status=AgentStatus.AVAILABLE,
            capabilities=[capability],
            priority=8,
        )
    )

    tool_registry = ToolRegistry()
    tool_registry.register(
        ToolDescriptor(
            name="education.search_course",
            display_name="Search course",
            description="Search courses.",
        ),
        handler=lambda payload, context: {
            "tenant_id": context.tenant_id,
            "query": payload["query"],
        },
    )

    discovery_result = AgentDiscovery(
        registry_service
    ).discover(
        DiscoveryCriteria(capability_name="course_search")
    )

    assert discovery_result is not None

    resolved_tools = CapabilityToolResolver(
        tool_registry
    ).resolve(discovery_result)

    assert [tool.name for tool in resolved_tools] == [
        "education.search_course"
    ]

    context = ToolExecutionContext(
        tenant_id="tenant.demo",
        agent_name=discovery_result.agent.name,
        capability_name=discovery_result.capability.name,
        workflow_execution_id="workflow.demo",
        workflow_step_id="step.search",
        correlation_id="corr.demo",
    )

    result = ToolInvoker(tool_registry).invoke_authorized(
        capability=discovery_result.capability,
        tool_name=resolved_tools[0].name,
        payload={"query": "biotechnology"},
        context=context,
    )

    assert result.success is True
    assert result.output == {
        "tenant_id": "tenant.demo",
        "query": "biotechnology",
    }
