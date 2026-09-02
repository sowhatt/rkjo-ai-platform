from rkjo_kernel.tools.context import ToolExecutionContext


def test_tool_execution_context_normalizes_identifiers():
    context = ToolExecutionContext(
        tenant_id=" Tenant-A ",
        agent_name=" Education.Agent ",
        capability_name=" Course_Search ",
        workflow_execution_id="exec-1",
        workflow_step_id="step-1",
        correlation_id="corr-1",
    )

    assert context.tenant_id == "tenant-a"
    assert context.agent_name == "education.agent"
    assert context.capability_name == "course_search"


def test_tool_execution_context_metadata_defaults_empty():
    context = ToolExecutionContext(
        tenant_id="tenant-a",
        agent_name="education.agent",
        capability_name="course_search",
    )

    assert context.metadata == {}
