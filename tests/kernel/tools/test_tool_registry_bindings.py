from rkjo_kernel.tools.binding import ToolBinding
from rkjo_kernel.tools.descriptor import ToolDescriptor
from rkjo_kernel.tools.registry import ToolRegistry


def test_registry_binds_tool_to_capability():
    registry = ToolRegistry()

    registry.register(
        ToolDescriptor(
            name="education.search_course",
            display_name="Search course",
            description="Search courses.",
        )
    )

    registry.bind(
        ToolBinding(
            capability_name="course_search",
            tool_name="education.search_course",
        )
    )

    tools = registry.find_by_capability(
        "course_search"
    )

    assert len(tools) == 1
    assert tools[0].name == "education.search_course"


def test_registry_ignores_duplicate_binding():
    registry = ToolRegistry()

    descriptor = ToolDescriptor(
        name="education.search_course",
        display_name="Search course",
        description="Search courses.",
    )

    registry.register(descriptor)

    binding = ToolBinding(
        capability_name="course_search",
        tool_name="education.search_course",
    )

    registry.bind(binding)
    registry.bind(binding)

    assert registry.count_bindings() == 1


def test_registry_rejects_binding_to_unknown_tool():
    registry = ToolRegistry()

    try:
        registry.bind(
            ToolBinding(
                capability_name="course_search",
                tool_name="missing.tool",
            )
        )
    except KeyError as exc:
        assert "not registered" in str(exc)
    else:
        raise AssertionError(
            "Expected KeyError for unknown tool."
        )
