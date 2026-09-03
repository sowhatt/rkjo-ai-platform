from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.registry.descriptor import AgentDescriptor, AgentStatus
from rkjo_kernel.registry.discovery import AgentDiscovery
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.tools.descriptor import ToolDescriptor
from rkjo_kernel.tools.invoker import ToolInvoker
from rkjo_kernel.tools.registry import ToolRegistry
from rkjo_kernel.tools.resolver import CapabilityToolResolver
from rkjo_kernel.workflow.capability_tool_execution_adapter import (
    CapabilityToolExecutionAdapter,
)
from rkjo_kernel.workflow.models.workflow_context import WorkflowContext
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep


def build_adapter(*, tools: list[str], register_tools: list[str]):
    agent_registry = AgentRegistry()
    registry_service = RegistryService(agent_registry)

    registry_service.register_agent(
        AgentDescriptor(
            name="education.agent",
            display_name="Education Agent",
            product="education",
            queue_name="education.agent",
            status=AgentStatus.AVAILABLE,
            capabilities=[
                AgentCapability(
                    name="course_search",
                    description="Search courses.",
                    tools=tools,
                )
            ],
        )
    )

    tool_registry = ToolRegistry()

    for tool_name in register_tools:
        tool_registry.register(
            ToolDescriptor(
                name=tool_name,
                display_name=tool_name,
                description=tool_name,
            ),
            handler=lambda payload, context: {
                "tenant_id": context.tenant_id,
                "agent_name": context.agent_name,
                "capability_name": context.capability_name,
                "payload": payload,
            },
        )

    return CapabilityToolExecutionAdapter(
        discovery=AgentDiscovery(registry_service),
        resolver=CapabilityToolResolver(tool_registry),
        invoker=ToolInvoker(tool_registry),
    )


def test_adapter_executes_single_declared_tool():
    adapter = build_adapter(
        tools=["education.search_course"],
        register_tools=["education.search_course"],
    )

    result = adapter.execute(
        step=WorkflowStep(
            step_id="search",
            name="Search course",
            capability_name="course_search",
        ),
        context=WorkflowContext(
            input_data={"query": "biotechnology"},
            metadata={"tenant_id": "tenant.demo"},
        ),
    )

    assert result.success is True
    assert result.output["tenant_id"] == "tenant.demo"
    assert result.output["agent_name"] == "education.agent"
    assert result.output["capability_name"] == "course_search"
    assert result.output["payload"] == {
        "query": "biotechnology"
    }
    assert result.metadata["tool_name"] == (
        "education.search_course"
    )


def test_adapter_requires_explicit_tool_when_capability_has_multiple_tools():
    adapter = build_adapter(
        tools=[
            "education.search_course",
            "education.get_course",
        ],
        register_tools=[
            "education.search_course",
            "education.get_course",
        ],
    )

    result = adapter.execute(
        step=WorkflowStep(
            step_id="search",
            name="Search course",
            capability_name="course_search",
        ),
        context=WorkflowContext(
            metadata={"tenant_id": "tenant.demo"},
        ),
    )

    assert result.success is False
    assert "tool_name" in result.error


def test_adapter_executes_explicit_declared_tool():
    adapter = build_adapter(
        tools=[
            "education.search_course",
            "education.get_course",
        ],
        register_tools=[
            "education.search_course",
            "education.get_course",
        ],
    )

    result = adapter.execute(
        step=WorkflowStep(
            step_id="get",
            name="Get course",
            capability_name="course_search",
            metadata={"tool_name": "education.get_course"},
        ),
        context=WorkflowContext(
            variables={"course_id": "course-1"},
            metadata={"tenant_id": "tenant.demo"},
        ),
    )

    assert result.success is True
    assert result.metadata["tool_name"] == "education.get_course"
    assert result.output["payload"] == {
        "course_id": "course-1"
    }


def test_adapter_denies_undeclared_explicit_tool():
    adapter = build_adapter(
        tools=["education.search_course"],
        register_tools=[
            "education.search_course",
            "education.delete_course",
        ],
    )

    result = adapter.execute(
        step=WorkflowStep(
            step_id="delete",
            name="Delete course",
            capability_name="course_search",
            metadata={"tool_name": "education.delete_course"},
        ),
        context=WorkflowContext(
            metadata={"tenant_id": "tenant.demo"},
        ),
    )

    assert result.success is False
    assert "not authorized" in result.error


def test_adapter_fails_closed_without_tenant_id():
    adapter = build_adapter(
        tools=["education.search_course"],
        register_tools=["education.search_course"],
    )

    result = adapter.execute(
        step=WorkflowStep(
            step_id="search",
            name="Search course",
            capability_name="course_search",
        ),
        context=WorkflowContext(),
    )

    assert result.success is False
    assert "tenant_id" in result.error
