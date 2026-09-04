from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.registry.descriptor import AgentDescriptor, AgentStatus
from rkjo_kernel.registry.discovery import AgentDiscovery
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.tools.context import ToolExecutionContext
from rkjo_kernel.tools.invoker import ToolInvoker
from rkjo_kernel.tools.mcp import MCPClient, MCPRemoteTool, MCPToolAdapter
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


class FakeEducationMCPClient(MCPClient):
    def list_tools(self) -> list[MCPRemoteTool]:
        return [
            MCPRemoteTool(
                name="search_courses",
                description="Search education courses",
            )
        ]

    def call_tool(
        self,
        *,
        tool_name: str,
        arguments: dict,
        context: ToolExecutionContext | None = None,
    ):
        return {
            "tool": tool_name,
            "matches": [arguments["query"]],
        }


def test_workflow_executes_authorized_mcp_tool_end_to_end():
    tool_registry = ToolRegistry()
    MCPToolAdapter(
        client=FakeEducationMCPClient(),
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

    adapter = CapabilityToolExecutionAdapter(
        discovery=AgentDiscovery(registry_service),
        resolver=CapabilityToolResolver(tool_registry),
        invoker=ToolInvoker(tool_registry),
    )

    execution = WorkflowExecution(
        definition=WorkflowDefinition(
            workflow_id="education.mcp-search",
            name="Education MCP search",
            steps=[
                WorkflowStep(
                    step_id="search",
                    name="Search through MCP",
                    capability_name="course_search",
                )
            ],
        ),
        context=WorkflowContext(
            input_data={"query": "biotechnology"},
            metadata={"tenant_id": "tenant.demo"},
        ),
    )

    result = WorkflowExecutor(adapter=adapter).execute(execution)

    assert result.status == WorkflowStatus.COMPLETED
    assert result.definition.steps[0].output == {
        "server": "education",
        "remote_tool": "search_courses",
        "tenant_id": "tenant.demo",
        "result": {
            "tool": "search_courses",
            "matches": ["biotechnology"],
        },
    }
