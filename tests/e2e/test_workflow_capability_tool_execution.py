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
from rkjo_kernel.workflow.executor import WorkflowExecutor
from rkjo_kernel.workflow.models.workflow_context import WorkflowContext
from rkjo_kernel.workflow.models.workflow_definition import WorkflowDefinition
from rkjo_kernel.workflow.models.workflow_execution import WorkflowExecution
from rkjo_kernel.workflow.models.workflow_status import WorkflowStatus
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep


def test_workflow_executes_discovered_authorized_tool_end_to_end():
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
                    description="Search education courses.",
                    tools=["education.search_course"],
                )
            ],
        )
    )

    tool_registry = ToolRegistry()
    tool_registry.register(
        ToolDescriptor(
            name="education.search_course",
            display_name="Search course",
            description="Search education courses.",
        ),
        handler=lambda payload, context: {
            "tenant_id": context.tenant_id,
            "query": payload["query"],
            "workflow_step_id": context.workflow_step_id,
        },
    )

    adapter = CapabilityToolExecutionAdapter(
        discovery=AgentDiscovery(registry_service),
        resolver=CapabilityToolResolver(tool_registry),
        invoker=ToolInvoker(tool_registry),
    )

    execution = WorkflowExecution(
        definition=WorkflowDefinition(
            workflow_id="education.course-search",
            name="Education course search",
            steps=[
                WorkflowStep(
                    step_id="search-course",
                    name="Search course",
                    capability_name="course_search",
                    position=0,
                )
            ],
        ),
        context=WorkflowContext(
            input_data={"query": "biotechnology"},
            metadata={
                "tenant_id": "tenant.demo",
                "workflow_execution_id": "workflow.demo",
                "correlation_id": "corr.demo",
            },
        ),
        execution_id="workflow.demo",
    )

    result = WorkflowExecutor(adapter=adapter).execute(execution)

    assert result.status == WorkflowStatus.COMPLETED
    assert result.definition.steps[0].output == {
        "tenant_id": "tenant.demo",
        "query": "biotechnology",
        "workflow_step_id": "search-course",
    }

    step_result = result.context.metadata["step_results"][
        "search-course"
    ]

    assert step_result["success"] is True
    assert step_result["metadata"]["tool_name"] == (
        "education.search_course"
    )
    assert step_result["metadata"]["selected_agent_name"] == (
        "education.agent"
    )
