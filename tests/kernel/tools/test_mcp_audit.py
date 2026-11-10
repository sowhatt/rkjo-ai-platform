from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.tools.context import ToolExecutionContext
from rkjo_kernel.tools.invoker import ToolInvoker
from rkjo_kernel.tools.mcp.adapter import MCPToolAdapter
from rkjo_kernel.tools.mcp.audit import InMemoryMCPAuditSink
from rkjo_kernel.tools.mcp.client import MCPClient, MCPRemoteTool
from rkjo_kernel.tools.registry import ToolRegistry


class AuditedMCPClient(MCPClient):
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def list_tools(self) -> list[MCPRemoteTool]:
        return [MCPRemoteTool(name="search_courses")]

    def call_tool(
        self,
        *,
        tool_name: str,
        arguments: dict,
        context: ToolExecutionContext | None = None,
    ):
        if self.fail:
            raise RuntimeError("remote failed")
        return {"ok": True}


def _invoke(*, client: MCPClient, audit_sink: InMemoryMCPAuditSink):
    registry = ToolRegistry()
    MCPToolAdapter(
        client=client,
        registry=registry,
        server_name="education",
        audit_sink=audit_sink,
    ).register_remote_tools()

    return ToolInvoker(registry).invoke_authorized(
        capability=AgentCapability(
            name="course_search",
            description="Search courses",
            tools=["mcp.education.search_courses"],
        ),
        tool_name="mcp.education.search_courses",
        payload={"query": "biotechnology"},
        context=ToolExecutionContext(
            tenant_id="tenant.demo",
            agent_name="education.agent",
            capability_name="course_search",
            workflow_execution_id="wf-123",
            workflow_step_id="search",
            correlation_id="corr-123",
        ),
    )


def test_mcp_adapter_audits_successful_execution():
    audit_sink = InMemoryMCPAuditSink()

    result = _invoke(
        client=AuditedMCPClient(),
        audit_sink=audit_sink,
    )

    assert result.success is True
    event = audit_sink.events[0]
    assert event.server_name == "education"
    assert event.remote_tool_name == "search_courses"
    assert event.tenant_id == "tenant.demo"
    assert event.agent_name == "education.agent"
    assert event.capability_name == "course_search"
    assert event.workflow_execution_id == "wf-123"
    assert event.workflow_step_id == "search"
    assert event.correlation_id == "corr-123"
    assert event.duration_ms >= 0
    assert event.success is True
    assert event.error_type is None


def test_mcp_adapter_audits_failed_execution_without_error_message():
    audit_sink = InMemoryMCPAuditSink()

    result = _invoke(
        client=AuditedMCPClient(fail=True),
        audit_sink=audit_sink,
    )

    assert result.success is False
    event = audit_sink.events[0]
    assert event.success is False
    assert event.error_type == "RuntimeError"
    assert event.metadata == {"transport": "mcp"}
