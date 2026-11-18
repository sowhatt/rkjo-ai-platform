import pytest

from rkjo_kernel.tools.descriptor import ToolDescriptor
from rkjo_kernel.tools.registry import ToolRegistry


def build_tool(name: str) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        display_name=name,
        description="test tool",
    )


def test_register_and_find_tool():
    registry = ToolRegistry()

    descriptor = build_tool("education.search_course")
    registry.register(descriptor)

    assert registry.find_by_name(
        "education.search_course"
    ) == descriptor


def test_register_replaces_existing_descriptor():
    registry = ToolRegistry()

    registry.register(
        build_tool("education.search_course")
    )

    updated = ToolDescriptor(
        name="education.search_course",
        display_name="Updated",
        description="updated tool",
        version="2.0.0",
    )

    registry.register(updated)

    assert registry.find_by_name(
        "education.search_course"
    ) == updated


def test_unregister_unknown_tool_raises():
    registry = ToolRegistry()

    with pytest.raises(KeyError):
        registry.unregister("missing.tool")


def test_list_tools():
    registry = ToolRegistry()

    registry.register(build_tool("tool.one"))
    registry.register(build_tool("tool.two"))

    assert len(registry.list_tools()) == 2
