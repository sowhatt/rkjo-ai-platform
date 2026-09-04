from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.tools.context import ToolExecutionContext
from rkjo_kernel.tools.invoker import ToolInvoker
from rkjo_kernel.tools.mcp import (
    MCPClient,
    MCPRemoteTool,
    MCPToolAdapter,
)
from rkjo_kernel.tools.registry import ToolRegistry


class FakeMCPClient(MCPClient):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict, str | None]] = []

    def list_tools(self) -> list[MCPRemoteTool]:
        return [
            MCPRemoteTool(
                name="search_courses",
                description="Search courses",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                },
            )
        ]

    def call_tool(
        self,
        *,
        tool_name: str,
        arguments: dict,
        context: ToolExecutionContext | None = None,
    ):
        self.calls.append(
            (
                tool_name,
                arguments,
                context.tenant_id if context else None,
            )
        )
        return {"items": [arguments["query"]]}


def test_adapter_registers_remote_tool_as_rkjo_tool():
    client = FakeMCPClient()
    registry = ToolRegistry()
    adapter = MCPToolAdapter(
        client=client,
        registry=registry,
        server_name="education",
    )

    registrations = adapter.register_remote_tools()

    assert registrations[0].remote_name == "search_courses"
    assert registrations[0].rkjo_name == "mcp.education.search_courses"

    descriptor = registry.find_by_name("mcp.education.search_courses")

    assert descriptor is not None
    assert descriptor.metadata["transport"] == "mcp"
    assert descriptor.metadata["mcp_server"] == "education"
    assert descriptor.input_schema["type"] == "object"


def test_registered_mcp_tool_executes_through_authorized_invoker():
    client = FakeMCPClient()
    registry = ToolRegistry()
    MCPToolAdapter(
        client=client,
        registry=registry,
        server_name="education",
    ).register_remote_tools()

    capability = AgentCapability(
        name="course_search",
        description="Search courses",
        tools=["mcp.education.search_courses"],
    )

    context = ToolExecutionContext(
        tenant_id="tenant.demo",
        agent_name="education.agent",
        capability_name="course_search",
    )

    result = ToolInvoker(registry).invoke_authorized(
        capability=capability,
        tool_name="mcp.education.search_courses",
        payload={"query": "biotechnology"},
        context=context,
    )

    assert result.success is True
    assert client.calls == [
        (
            "search_courses",
            {"query": "biotechnology"},
            "tenant.demo",
        )
    ]
    assert result.output == {
        "server": "education",
        "remote_tool": "search_courses",
        "tenant_id": "tenant.demo",
        "result": {"items": ["biotechnology"]},
    }


def test_registered_mcp_tool_is_denied_when_not_declared():
    client = FakeMCPClient()
    registry = ToolRegistry()
    MCPToolAdapter(
        client=client,
        registry=registry,
        server_name="education",
    ).register_remote_tools()

    capability = AgentCapability(
        name="course_search",
        description="Search courses",
        tools=[],
    )

    result = ToolInvoker(registry).invoke_authorized(
        capability=capability,
        tool_name="mcp.education.search_courses",
        payload={"query": "biotechnology"},
        context=ToolExecutionContext(
            tenant_id="tenant.demo",
            agent_name="education.agent",
            capability_name="course_search",
        ),
    )

    assert result.success is False
    assert "not authorized" in result.error
    assert client.calls == []
