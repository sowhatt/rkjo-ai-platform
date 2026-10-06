import pytest

from rkjo_kernel.tools.context import ToolExecutionContext


def test_routing_identifiers_are_normalized_but_execution_identity_is_preserved():
    context = ToolExecutionContext(
        tenant_id=" Tenant-A ",
        agent_name=" Agent-A ",
        capability_name=" Capability-A ",
        mission_id=" Mission-ABC ",
        trace_id=" Trace-XYZ ",
        workflow_execution_id=" Workflow-01 ",
        workflow_step_id=" Step-01 ",
        correlation_id=" Correlation-01 ",
    )

    assert context.tenant_id == "tenant-a"
    assert context.agent_name == "agent-a"
    assert context.capability_name == "capability-a"
    assert context.mission_id == "Mission-ABC"
    assert context.trace_id == "Trace-XYZ"
    assert context.workflow_execution_id == "Workflow-01"
    assert context.workflow_step_id == "Step-01"
    assert context.correlation_id == "Correlation-01"


def test_optional_execution_identity_accepts_none():
    context = ToolExecutionContext(
        tenant_id="tenant-a",
        agent_name="agent-a",
        capability_name="capability-a",
    )
    assert context.mission_id is None
    assert context.trace_id is None


@pytest.mark.parametrize("field", ["mission_id", "trace_id"])
def test_explicit_blank_execution_identity_is_rejected(field):
    values = {
        "tenant_id": "tenant-a",
        "agent_name": "agent-a",
        "capability_name": "capability-a",
        field: "   ",
    }
    with pytest.raises(ValueError, match="Execution identity"):
        ToolExecutionContext(**values)
