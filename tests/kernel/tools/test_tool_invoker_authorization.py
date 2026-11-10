from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.tools.context import ToolExecutionContext
from rkjo_kernel.tools.descriptor import ToolDescriptor
from rkjo_kernel.tools.invoker import ToolInvoker
from rkjo_kernel.tools.registry import ToolRegistry


def build_context(
    capability_name: str = "course_search",
) -> ToolExecutionContext:
    return ToolExecutionContext(
        tenant_id="tenant.demo",
        agent_name="education.agent",
        capability_name=capability_name,
    )


def build_capability() -> AgentCapability:
    return AgentCapability(
        name="course_search",
        description="Search education courses.",
        tools=["education.search_course"],
    )


def test_authorized_invocation_executes_declared_tool():
    registry = ToolRegistry()
    registry.register(
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

    result = ToolInvoker(registry).invoke_authorized(
        capability=build_capability(),
        tool_name="education.search_course",
        payload={"query": "biotechnology"},
        context=build_context(),
    )

    assert result.success is True
    assert result.output == {
        "tenant_id": "tenant.demo",
        "query": "biotechnology",
    }


def test_authorized_invocation_denies_undeclared_tool_before_handler():
    registry = ToolRegistry()
    handler_called = False

    def handler(payload, context):
        nonlocal handler_called
        handler_called = True
        return "deleted"

    registry.register(
        ToolDescriptor(
            name="education.delete_course",
            display_name="Delete course",
            description="Delete a course.",
        ),
        handler=handler,
    )

    result = ToolInvoker(registry).invoke_authorized(
        capability=build_capability(),
        tool_name="education.delete_course",
        payload={},
        context=build_context(),
    )

    assert result.success is False
    assert "not authorized" in result.error
    assert handler_called is False


def test_authorized_invocation_denies_context_capability_mismatch():
    registry = ToolRegistry()
    registry.register(
        ToolDescriptor(
            name="education.search_course",
            display_name="Search course",
            description="Search courses.",
        ),
        handler=lambda payload, context: "should-not-run",
    )

    result = ToolInvoker(registry).invoke_authorized(
        capability=build_capability(),
        tool_name="education.search_course",
        payload={},
        context=build_context("student_management"),
    )

    assert result.success is False
    assert "not authorized" in result.error


def test_authorized_invocation_keeps_unknown_registered_tool_failure():
    result = ToolInvoker(ToolRegistry()).invoke_authorized(
        capability=build_capability(),
        tool_name="education.search_course",
        payload={},
        context=build_context(),
    )

    assert result.success is False
    assert "not registered" in result.error
