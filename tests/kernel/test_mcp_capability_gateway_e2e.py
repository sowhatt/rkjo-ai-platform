from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.registry.descriptor import AgentDescriptor, AgentStatus
from rkjo_kernel.registry.discovery import AgentDiscovery
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.tools.context import ToolExecutionContext
from rkjo_kernel.tools.invoker import ToolInvoker
from rkjo_kernel.tools.mcp.adapter import MCPToolAdapter
from rkjo_kernel.tools.mcp.audit import InMemoryMCPAuditSink
from rkjo_kernel.tools.mcp.credentials import MappingMCPCredentialProvider
from rkjo_kernel.tools.mcp.runtime_client import TransportMCPClient
from rkjo_kernel.tools.mcp.transport import MCPTransport
from rkjo_kernel.tools.registry import ToolRegistry
from rkjo_kernel.tools.resolver import CapabilityToolResolver
from rkjo_kernel.workflow.capability_tool_execution_adapter import (
    CapabilityToolExecutionAdapter,
)
from rkjo_kernel.workflow.models.workflow_context import WorkflowContext
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep


class RecordingTransport(MCPTransport):
    def __init__(self):
        self.requests = []

    def request(self, *, method, params, headers, timeout_ms):
        self.requests.append({
            "method": method,
            "params": params,
            "headers": dict(headers),
            "timeout_ms": timeout_ms,
        })
        if method == "tools/list":
            return {
                "tools": [{
                    "name": "ping",
                    "description": "Tenant-aware ping",
                    "inputSchema": {"type": "object"},
                }]
            }
        if method == "tools/call":
            return {"content": [{"type": "text", "text": "pong"}]}
        raise AssertionError(method)


def build_stack(*, credentials):
    transport = RecordingTransport()
    client = TransportMCPClient(
        transport=transport,
        server_name="demo",
        credential_provider=MappingMCPCredentialProvider(credentials),
    )
    tools = ToolRegistry()
    audit = InMemoryMCPAuditSink()
    MCPToolAdapter(
        client=client,
        registry=tools,
        server_name="demo",
        audit_sink=audit,
    ).register_remote_tools()

    capability = AgentCapability(
        name="remote_ping",
        description="Call remote ping",
        tools=["mcp.demo.ping"],
    )
    agent = AgentDescriptor(
        name="demo.agent",
        display_name="Demo Agent",
        product="RKJO",
        queue_name="demo",
        status=AgentStatus.AVAILABLE,
        capabilities=[capability],
    )
    registry = AgentRegistry()
    RegistryService(registry).register_agent(agent)
    adapter = CapabilityToolExecutionAdapter(
        discovery=AgentDiscovery(RegistryService(registry)),
        resolver=CapabilityToolResolver(tools),
        invoker=ToolInvoker(tools),
    )
    return adapter, transport, audit


def test_capability_tool_gateway_mcp_e2e_preserves_security_identity():
    adapter, transport, audit = build_stack(
        credentials={
            ("tenant-a", "demo"): {"Authorization": "Bearer tenant-a-token"}
        }
    )
    step = WorkflowStep(
        step_id="step-1",
        name="remote ping",
        capability_name="remote_ping",
    )
    context = WorkflowContext(
        input_data={"message": "hello"},
        metadata={
            "tenant_id": "tenant-a",
            "mission_id": "Mission-ABC",
            "trace_id": "Trace-XYZ",
            "workflow_execution_id": "Workflow-01",
            "correlation_id": "Correlation-01",
        },
    )

    result = adapter.execute(step=step, context=context)

    assert result.success is True
    call = [r for r in transport.requests if r["method"] == "tools/call"][0]
    assert call["headers"]["Authorization"] == "Bearer tenant-a-token"
    assert call["params"]["name"] == "ping"
    assert len(audit.events) == 1
    event = audit.events[0]
    assert event.tenant_id == "tenant-a"
    assert event.mission_id == "Mission-ABC"
    assert event.trace_id == "Trace-XYZ"
    assert event.workflow_execution_id == "Workflow-01"
    assert event.workflow_step_id == "step-1"
    assert event.correlation_id == "Correlation-01"


def test_mcp_credentials_fail_closed_for_unconfigured_tenant():
    adapter, transport, audit = build_stack(
        credentials={
            ("tenant-a", "demo"): {"Authorization": "Bearer tenant-a-token"}
        }
    )
    result = adapter.execute(
        step=WorkflowStep(
            step_id="step-1",
            name="remote ping",
            capability_name="remote_ping",
        ),
        context=WorkflowContext(
            metadata={
                "tenant_id": "tenant-b",
                "mission_id": "Mission-B",
                "trace_id": "Trace-B",
            }
        ),
    )

    assert result.success is False
    assert "No MCP credentials configured" in result.error
    assert not [r for r in transport.requests if r["method"] == "tools/call"]
    assert len(audit.events) == 1
    assert audit.events[0].tenant_id == "tenant-b"
    assert audit.events[0].success is False
    assert audit.events[0].error_type == "PermissionError"


def test_transport_mcp_client_requires_execution_context_for_call():
    transport = RecordingTransport()
    client = TransportMCPClient(
        transport=transport,
        server_name="demo",
    )
    try:
        client.call_tool(tool_name="ping", arguments={}, context=None)
    except PermissionError:
        pass
    else:
        raise AssertionError("MCP call without context must fail closed")

    assert transport.requests == []
