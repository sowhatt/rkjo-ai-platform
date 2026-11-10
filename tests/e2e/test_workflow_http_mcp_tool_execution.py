import json

from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.registry.descriptor import AgentDescriptor, AgentStatus
from rkjo_kernel.registry.discovery import AgentDiscovery
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.tools.invoker import ToolInvoker
from rkjo_kernel.tools.mcp import (
    HTTPMCPTransport,
    MCPToolAdapter,
    MappingMCPCredentialProvider,
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


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._body


def test_workflow_executes_tenant_authorized_tool_over_http_mcp():
    captured_requests = []

    def opener(request, timeout):
        body = json.loads(request.data.decode("utf-8"))
        captured_requests.append((request, body, timeout))

        if body["method"] == "tools/list":
            return FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "result": {
                        "tools": [
                            {
                                "name": "search_courses",
                                "description": "Search courses",
                                "inputSchema": {"type": "object"},
                            }
                        ]
                    },
                }
            )

        return FakeResponse(
            {
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": body["params"]["arguments"]["query"],
                        }
                    ]
                },
            }
        )

    tool_registry = ToolRegistry()
    transport = HTTPMCPTransport(
        endpoint="https://education.example.test/mcp",
        opener=opener,
    )
    client = TransportMCPClient(
        transport=transport,
        server_name="education",
        credential_provider=MappingMCPCredentialProvider(
            {
                ("tenant.demo", "education"): {
                    "Authorization": "Bearer tenant-token",
                }
            }
        ),
    )
    MCPToolAdapter(
        client=client,
        registry=tool_registry,
        server_name="education",
    ).register_remote_tools()

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
                    description="Search courses through MCP",
                    tools=["mcp.education.search_courses"],
                )
            ],
        )
    )

    execution = WorkflowExecution(
        definition=WorkflowDefinition(
            workflow_id="education.http-mcp-search",
            name="Education HTTP MCP search",
            steps=[
                WorkflowStep(
                    step_id="search",
                    name="Search through HTTP MCP",
                    capability_name="course_search",
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
    assert result.definition.steps[0].output["result"]["content"][0]["text"] == (
        "biotechnology"
    )

    call_request, call_body, _ = captured_requests[-1]
    headers = {key.lower(): value for key, value in call_request.header_items()}

    assert call_body["method"] == "tools/call"
    assert headers["authorization"] == "Bearer tenant-token"
    assert headers["mcp-protocol-version"] == "2026-07-28"
    assert headers["mcp-method"] == "tools/call"
    assert headers["mcp-name"] == "search_courses"
