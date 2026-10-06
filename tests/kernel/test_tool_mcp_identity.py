from rkjo_kernel.tools.context import ToolExecutionContext
from rkjo_kernel.tools.mcp.audit import InMemoryMCPAuditSink
from rkjo_kernel.tools.mcp.adapter import MCPToolAdapter
from rkjo_kernel.tools.mcp.client import MCPClient, MCPRemoteTool
from rkjo_kernel.tools.registry import ToolRegistry


class Client(MCPClient):
    def list_tools(self):
        return [MCPRemoteTool(name="ping", description="ping")]

    def call_tool(self, *, tool_name, arguments, context=None):
        return {"ok": True}


def test_mcp_audit_preserves_mission_and_trace_identity():
    registry = ToolRegistry()
    audit = InMemoryMCPAuditSink()
    MCPToolAdapter(
        client=Client(),
        registry=registry,
        server_name="demo",
        audit_sink=audit,
    ).register_remote_tools()

    registered = registry.get_registered_tool("mcp.demo.ping")
    context = ToolExecutionContext(
        tenant_id="tenant-a",
        agent_name="agent-a",
        capability_name="ping",
        mission_id="mission-1",
        trace_id="trace-1",
    )

    registered.handler({}, context)

    assert len(audit.events) == 1
    assert audit.events[0].tenant_id == "tenant-a"
    assert audit.events[0].mission_id == "mission-1"
    assert audit.events[0].trace_id == "trace-1"
