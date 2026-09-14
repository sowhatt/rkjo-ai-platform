import pytest

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.mission import ExecutionContext


def test_execution_context_builds_immutable_execution_path():
    root = ExecutionContext(
        mission_id="mission-1",
        tenant_id="tenant-1",
        user_id="user-1",
        correlation_id="corr-1",
    )

    workflow = root.for_workflow("workflow-1")
    step = workflow.for_step("step-1")
    agent = step.for_agent("tutor-agent", "explain_fraction")
    tool = agent.for_tool_call("tool-call-1")

    assert root.workflow_execution_id is None
    assert tool.mission_id == "mission-1"
    assert tool.trace_id == root.trace_id
    assert tool.workflow_execution_id == "workflow-1"
    assert tool.step_id == "step-1"
    assert tool.agent_id == "tutor-agent"
    assert tool.capability_name == "explain_fraction"
    assert tool.tool_call_id == "tool-call-1"


def test_execution_context_serializes_runtime_metadata_keys():
    context = (
        ExecutionContext(mission_id="mission-1", trace_id="trace-1")
        .for_workflow("workflow-1")
        .for_step("step-1")
        .for_agent("agent-1", "CAPABILITY_ONE")
    )

    metadata = context.as_metadata()

    assert metadata["mission_id"] == "mission-1"
    assert metadata["trace_id"] == "trace-1"
    assert metadata["workflow_execution_id"] == "workflow-1"
    assert metadata["workflow_step_id"] == "step-1"
    assert metadata["agent_id"] == "agent-1"
    assert metadata["capability_name"] == "capability_one"
    assert "tool_call_id" not in metadata


def test_execution_context_injects_into_existing_agent_message_metadata():
    message = AgentMessage(
        source="orchestrator",
        target="tutor-agent",
        payload={"question": "What is 1/2?"},
        metadata={"attempt": 1},
    )
    context = (
        ExecutionContext(
            mission_id="mission-1",
            trace_id="trace-1",
            correlation_id=message.correlation_id,
        )
        .for_workflow("workflow-1")
        .for_step("step-1")
        .for_agent("tutor-agent", "explain_fraction")
    )

    context.inject_into(message.metadata)

    assert message.metadata["attempt"] == 1
    assert message.metadata["mission_id"] == "mission-1"
    assert message.metadata["trace_id"] == "trace-1"
    assert message.metadata["workflow_execution_id"] == "workflow-1"
    assert message.metadata["workflow_step_id"] == "step-1"
    assert message.metadata["capability_name"] == "explain_fraction"


def test_execution_context_rejects_empty_identifiers():
    with pytest.raises(ValueError, match="mission_id"):
        ExecutionContext(mission_id="  ")

    context = ExecutionContext(mission_id="mission-1")

    with pytest.raises(ValueError, match="step_id"):
        context.for_step("  ")
