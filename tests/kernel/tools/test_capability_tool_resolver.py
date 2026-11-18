import pytest

from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.registry.descriptor import AgentDescriptor
from rkjo_kernel.registry.discovery import DiscoveryResult
from rkjo_kernel.tools.descriptor import ToolDescriptor
from rkjo_kernel.tools.registry import ToolRegistry
from rkjo_kernel.tools.resolver import CapabilityToolResolver


def build_discovery_result(
    tools: list[str],
) -> DiscoveryResult:
    capability = AgentCapability(
        name="course_search",
        description="Search courses.",
        tools=tools,
    )

    agent = AgentDescriptor(
        name="education.agent",
        display_name="Education Agent",
        description="Education agent",
        product="education",
        queue_name="education.agent",
        capabilities=[capability],
    )

    return DiscoveryResult(
        agent=agent,
        capability=capability,
        score=1.0,
    )


def test_resolver_returns_registered_declared_tools():
    registry = ToolRegistry()

    registry.register(
        ToolDescriptor(
            name="education.search_course",
            display_name="Search course",
            description="Search courses.",
        )
    )

    registry.register(
        ToolDescriptor(
            name="education.get_course",
            display_name="Get course",
            description="Get course.",
        )
    )

    result = build_discovery_result(
        [
            "education.search_course",
            "education.get_course",
        ]
    )

    tools = CapabilityToolResolver(
        registry
    ).resolve(result)

    assert [
        tool.name
        for tool in tools
    ] == [
        "education.search_course",
        "education.get_course",
    ]


def test_resolver_returns_empty_when_capability_has_no_tools():
    registry = ToolRegistry()

    result = build_discovery_result([])

    tools = CapabilityToolResolver(
        registry
    ).resolve(result)

    assert tools == []


def test_resolver_raises_when_declared_tool_is_not_registered():
    registry = ToolRegistry()

    result = build_discovery_result(
        ["education.missing_tool"]
    )

    with pytest.raises(KeyError) as exc:
        CapabilityToolResolver(
            registry
        ).resolve(result)

    assert "education.missing_tool" in str(
        exc.value
    )
    assert "not registered" in str(
        exc.value
    )


def test_resolver_preserves_capability_tool_order():
    registry = ToolRegistry()

    registry.register(
        ToolDescriptor(
            name="tool.second",
            display_name="Second",
            description="Second tool",
        )
    )

    registry.register(
        ToolDescriptor(
            name="tool.first",
            display_name="First",
            description="First tool",
        )
    )

    result = build_discovery_result(
        [
            "tool.first",
            "tool.second",
        ]
    )

    tools = CapabilityToolResolver(
        registry
    ).resolve(result)

    assert [
        tool.name
        for tool in tools
    ] == [
        "tool.first",
        "tool.second",
    ]
