import pytest

from rkjo_kernel.workflow import (
    AgentExecutionAdapter,
    ExecutionResult,
    WorkflowContext,
    WorkflowStep,
)


class SuccessfulAdapter(AgentExecutionAdapter):
    def execute(
        self,
        *,
        step: WorkflowStep,
        context: WorkflowContext,
    ) -> ExecutionResult:
        return ExecutionResult.succeeded(
            output={
                "step_id": step.step_id,
                "request_id": context.get("request_id"),
            },
            metadata={
                "agent_name": step.agent_name,
            },
        )


class FailedAdapter(AgentExecutionAdapter):
    def execute(
        self,
        *,
        step: WorkflowStep,
        context: WorkflowContext,
    ) -> ExecutionResult:
        return ExecutionResult.failed(
            error=f"Agent unavailable: {step.agent_name}",
        )


def create_step() -> WorkflowStep:
    return WorkflowStep(
        step_id="validate",
        name="Validate request",
        agent_name="validation_agent",
        position=0,
    )


def test_adapter_is_abstract():
    with pytest.raises(TypeError):
        AgentExecutionAdapter()


def test_concrete_adapter_returns_success_result():
    adapter = SuccessfulAdapter()
    context = WorkflowContext(
        input_data={"request_id": "REQ-001"}
    )

    result = adapter.execute(
        step=create_step(),
        context=context,
    )

    assert result.success is True
    assert result.output == {
        "step_id": "validate",
        "request_id": "REQ-001",
    }
    assert result.metadata == {
        "agent_name": "validation_agent"
    }


def test_concrete_adapter_returns_failure_result():
    adapter = FailedAdapter()

    result = adapter.execute(
        step=create_step(),
        context=WorkflowContext(),
    )

    assert result.success is False
    assert result.error == (
        "Agent unavailable: validation_agent"
    )
