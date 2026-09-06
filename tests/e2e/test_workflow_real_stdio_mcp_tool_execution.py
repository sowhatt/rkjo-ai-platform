import importlib.metadata
import json
import sys
from pathlib import Path

import pytest

from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.registry.descriptor import AgentDescriptor, AgentStatus
from rkjo_kernel.registry.discovery import AgentDiscovery
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.tools.invoker import ToolInvoker
from rkjo_kernel.tools.mcp import (
    InMemoryMCPAuditSink,
    MCPToolAdapter,
    StdioMCPTransport,
    TransportMCPClient,
)
from rkjo_kernel.tools.registry import ToolRegistry
from rkjo_kernel.tools.resolver import CapabilityToolResolver
from rkjo_kernel.workflow.capability_tool_execution_adapter import (
    CapabilityToolExecutionAdapter,
)
from rkjo_kernel.workflow.executor import WorkflowExecutor
from rkjo_kernel.workflow.models.workflow_context import WorkflowContext
from rkjo_kernel.workflow.models.workflow_definition import WorkflowDefinition
from rkjo_kernel.workflow.models.workflow_execution import WorkflowExecution
from rkjo_kernel.workflow.models.workflow_status import WorkflowStatus
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep


def _require_mcp_v2() -> None:
    try:
        version = importlib.metadata.version("mcp")
    except importlib.metadata.PackageNotFoundError:
        pytest.skip("MCP SDK v2 is not installed; install requirements-mcp-test.txt")

    major = int(version.split(".", 1)[0])
    if major < 2:
        pytest.skip(f"MCP SDK v2 is required; installed version is {version}")


def test_workflow_executes_real_mcp_server_over_stdio():
    _require_mcp_v2()

    server_path = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "mcp"
        / "real_course_server.py"
    )

    tool_registry = ToolRegistry()
    audit_sink = InMemoryMCPAuditSink()
    transport = StdioMCPTransport(
        command=sys.executable,
        args=[str(server_path)],
    )
    client = TransportMCPClient(
        transport=transport,
        server_name="education-real",
        timeout_ms=10_000,
    )

    registrations = MCPToolAdapter(
        client=client,
        registry=tool_registry,
        server_name="education-real",
        audit_sink=audit_sink,
    ).register_remote_tools()

    assert [registration.remote_name for registration in registrations] == [
        "search_courses"
    ]
    assert registrations[0].rkjo_name == "mcp.education-real.search_courses"

    agent_registry = AgentRegistry()
    registry_service = RegistryService(agent_registry)
    registry_service.register_agent(
        AgentDescriptor(
            name="education.real-agent",
            display_name="Real Education MCP Agent",
            product="education",
            queue_name="education.real-agent",
            status=AgentStatus.AVAILABLE,
            capabilities=[
                AgentCapability(
                    name="real_course_search",
                    description="Search courses through a real MCP server",
                    tools=["mcp.education-real.search_courses"],
                )
            ],
        )
    )

    execution = WorkflowExecution(
        definition=WorkflowDefinition(
            workflow_id="education.real-stdio-mcp-search",
            name="Education real stdio MCP search",
            steps=[
                WorkflowStep(
                    step_id="search",
                    name="Search through real stdio MCP",
                    capability_name="real_course_search",
                )
            ],
        ),
        context=WorkflowContext(
            input_data={"query": "biotechnology"},
            metadata={"tenant_id": "tenant.demo"},
        ),
    )

    result = WorkflowExecutor(
        adapter=CapabilityToolExecutionAdapter(
            discovery=AgentDiscovery(registry_service),
            resolver=CapabilityToolResolver(tool_registry),
            invoker=ToolInvoker(tool_registry),
        )
    ).execute(execution)

    assert result.status == WorkflowStatus.COMPLETED

    output = result.definition.steps[0].output
    serialized_output = json.dumps(output, sort_keys=True)
    assert "Biotechnology Fundamentals" in serialized_output
    assert "Agricultural Biotechnology" in serialized_output

    assert len(audit_sink.events) == 1
    event = audit_sink.events[0]
    assert event.server_name == "education-real"
    assert event.remote_tool_name == "search_courses"
    assert event.tenant_id == "tenant.demo"
    assert event.capability_name == "real_course_search"
    assert event.success is True
