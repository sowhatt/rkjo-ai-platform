import pytest

from rkjo_kernel.workflow import (
    AgentExecutionAdapter,
    ExecutionResult,
    InvalidWorkflowTransitionError,
    StepStatus,
    WorkflowDefinition,
    WorkflowEngine,
    WorkflowExecutor,
    WorkflowStatus,
    WorkflowStep,
)


def create_definition() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id="customer.processing",
        name="Customer processing",
        steps=[
            WorkflowStep(
                step_id="validate",
                name="Validate customer",
                agent_name="validation_agent",
                position=0,
            ),
            WorkflowStep(
                step_id="execute",
                name="Execute operation",
                agent_name="execution_agent",
                position=1,
            ),
        ],
    )


class RecordingAdapter(AgentExecutionAdapter):
    def __init__(self) -> None:
        self.calls: list[str] = []

    def execute(
        self,
        *,
        step,
        context,
    ) -> ExecutionResult:
        self.calls.append(step.step_id)

        previous_output = context.outputs.get("validate")

        return ExecutionResult.succeeded(
            output={
                "step_id": step.step_id,
                "previous_output": previous_output,
            },
            metadata={
                "agent_name": step.agent_name,
            },
            duration_ms=5.0,
        )


class FailedAdapter(AgentExecutionAdapter):
    def execute(
        self,
        *,
        step,
        context,
    ) -> ExecutionResult:
        return ExecutionResult.failed(
            error=f"Execution failed for {step.step_id}",
            metadata={
                "agent_name": step.agent_name,
            },
        )


class ExceptionAdapter(AgentExecutionAdapter):
    def execute(
        self,
        *,
        step,
        context,
    ) -> ExecutionResult:
        raise RuntimeError("Agent connection lost")


class InvalidResultAdapter(AgentExecutionAdapter):
    def execute(
        self,
        *,
        step,
        context,
    ):
        return {
            "success": True,
        }


def test_executor_runs_all_steps_to_completion():
    engine = WorkflowEngine()
    adapter = RecordingAdapter()
    executor = WorkflowExecutor(
        adapter=adapter,
        engine=engine,
    )
    execution = engine.create_execution(
        create_definition()
    )

    result = executor.execute(execution)

    assert result is execution
    assert execution.status == WorkflowStatus.COMPLETED
    assert adapter.calls == [
        "validate",
        "execute",
    ]
    assert all(
        step.status == StepStatus.COMPLETED
        for step in execution.definition.steps
    )


def test_executor_makes_previous_output_available():
    engine = WorkflowEngine()
    adapter = RecordingAdapter()
    executor = WorkflowExecutor(
        adapter=adapter,
        engine=engine,
    )
    execution = engine.create_execution(
        create_definition()
    )

    executor.execute(execution)

    validate_output = execution.context.outputs[
        "validate"
    ]
    execute_output = execution.context.outputs[
        "execute"
    ]

    assert validate_output == {
        "step_id": "validate",
        "previous_output": None,
    }
    assert execute_output["previous_output"] == (
        validate_output
    )


def test_executor_starts_pending_execution_automatically():
    engine = WorkflowEngine()
    executor = WorkflowExecutor(
        adapter=RecordingAdapter(),
        engine=engine,
    )
    execution = engine.create_execution(
        create_definition()
    )

    assert execution.status == WorkflowStatus.PENDING

    executor.execute(execution)

    assert execution.started_at is not None
    assert execution.status == WorkflowStatus.COMPLETED


def test_executor_resumes_running_execution():
    engine = WorkflowEngine()
    adapter = RecordingAdapter()
    executor = WorkflowExecutor(
        adapter=adapter,
        engine=engine,
    )
    execution = engine.create_execution(
        create_definition()
    )
    engine.start(execution)

    executor.execute(execution)

    assert execution.status == WorkflowStatus.COMPLETED
    assert adapter.calls == [
        "validate",
        "execute",
    ]


def test_execute_next_processes_only_one_step():
    engine = WorkflowEngine()
    adapter = RecordingAdapter()
    executor = WorkflowExecutor(
        adapter=adapter,
        engine=engine,
    )
    execution = engine.create_execution(
        create_definition()
    )
    engine.start(execution)

    result = executor.execute_next(execution)

    assert result is not None
    assert result.success is True
    assert adapter.calls == ["validate"]
    assert execution.definition.steps[0].status == (
        StepStatus.COMPLETED
    )
    assert execution.definition.steps[1].status == (
        StepStatus.PENDING
    )
    assert execution.status == WorkflowStatus.RUNNING


def test_failed_result_stops_workflow():
    engine = WorkflowEngine()
    executor = WorkflowExecutor(
        adapter=FailedAdapter(),
        engine=engine,
    )
    execution = engine.create_execution(
        create_definition()
    )

    executor.execute(execution)

    assert execution.status == WorkflowStatus.FAILED
    assert execution.error == (
        "Execution failed for validate"
    )
    assert execution.definition.steps[0].status == (
        StepStatus.FAILED
    )
    assert execution.definition.steps[1].status == (
        StepStatus.PENDING
    )


def test_adapter_exception_is_converted_to_failure():
    engine = WorkflowEngine()
    executor = WorkflowExecutor(
        adapter=ExceptionAdapter(),
        engine=engine,
    )
    execution = engine.create_execution(
        create_definition()
    )

    executor.execute(execution)

    assert execution.status == WorkflowStatus.FAILED
    assert execution.error == (
        "RuntimeError: Agent connection lost"
    )

    metadata = execution.context.metadata[
        "step_results"
    ]["validate"]

    assert metadata["success"] is False
    assert metadata["metadata"] == {
        "exception_type": "RuntimeError"
    }


def test_invalid_adapter_result_fails_workflow():
    engine = WorkflowEngine()
    executor = WorkflowExecutor(
        adapter=InvalidResultAdapter(),
        engine=engine,
    )
    execution = engine.create_execution(
        create_definition()
    )

    executor.execute(execution)

    assert execution.status == WorkflowStatus.FAILED
    assert execution.error == (
        "AgentExecutionAdapter must return "
        "an ExecutionResult."
    )

    metadata = execution.context.metadata[
        "step_results"
    ]["validate"]

    assert metadata["metadata"] == {
        "returned_type": "dict"
    }


def test_executor_rejects_terminal_execution():
    engine = WorkflowEngine()
    executor = WorkflowExecutor(
        adapter=RecordingAdapter(),
        engine=engine,
    )
    execution = engine.create_execution(
        create_definition()
    )
    engine.cancel(execution)

    with pytest.raises(
        InvalidWorkflowTransitionError,
        match="pending or running",
    ):
        executor.execute(execution)
