from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.registry.discovery import (
    AgentDiscovery,
    DiscoveryCriteria,
)
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.tools.descriptor import ToolDescriptor
from rkjo_kernel.tools.registry import ToolRegistry
from rkjo_kernel.tools.resolver import CapabilityToolResolver


def test_discovery_selects_agent_and_resolves_declared_tools():
    agent_registry = AgentRegistry()
    registry_service = RegistryService(
        agent_registry
    )

    capability = AgentCapability(
        name="course_search",
        description="Search education courses.",
        tools=[
            "education.search_course",
            "education.get_course",
        ],
    )

    registry_service.register_agent(
        AgentDescriptor(
            name="education.agent",
            display_name="Education Agent",
            description="Education agent",
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
        )
    )

    tool_registry.register(
        ToolDescriptor(
            name="education.get_course",
            display_name="Get course",
            description="Get course.",
        )
    )

    discovery_result = AgentDiscovery(
        registry_service
    ).discover(
        DiscoveryCriteria(
            capability_name="course_search"
        )
    )

    assert discovery_result is not None
    assert (
        discovery_result.agent.name
        == "education.agent"
    )
    assert (
        discovery_result.capability.name
        == "course_search"
    )

    tools = CapabilityToolResolver(
        tool_registry
    ).resolve(
        discovery_result
    )

    assert [
        tool.name
        for tool in tools
    ] == [
        "education.search_course",
        "education.get_course",
    ]
