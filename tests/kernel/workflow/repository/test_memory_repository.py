from rkjo_kernel.workflow.models.workflow_definition import WorkflowDefinition
from rkjo_kernel.workflow.models.workflow_execution import WorkflowExecution
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep
from rkjo_kernel.workflow.repository.memory import InMemoryWorkflowRepository


def make_execution(
    *,
    execution_id: str = "execution-001",
) -> WorkflowExecution:
    definition = WorkflowDefinition(
        workflow_id="workflow-001",
        name="Test Workflow",
        steps=[
            WorkflowStep(
                step_id="step-001",
                name="Test Step",
                agent_name="test-agent",
            )
        ],
    )

    return WorkflowExecution(
        definition=definition,
        execution_id=execution_id,
    )


def test_save_and_get_execution():
    repository = InMemoryWorkflowRepository()
    execution = make_execution()

    repository.save(execution)

    stored = repository.get(execution.execution_id)

    assert stored is not None
    assert stored.execution_id == execution.execution_id
    assert stored.definition.workflow_id == "workflow-001"


def test_get_unknown_execution_returns_none():
    repository = InMemoryWorkflowRepository()

    assert repository.get("unknown") is None


def test_exists_returns_true_after_save():
    repository = InMemoryWorkflowRepository()
    execution = make_execution()

    repository.save(execution)

    assert repository.exists(execution.execution_id) is True


def test_exists_returns_false_for_unknown_execution():
    repository = InMemoryWorkflowRepository()

    assert repository.exists("unknown") is False


def test_delete_removes_execution():
    repository = InMemoryWorkflowRepository()
    execution = make_execution()

    repository.save(execution)
    repository.delete(execution.execution_id)

    assert repository.exists(execution.execution_id) is False
    assert repository.get(execution.execution_id) is None


def test_delete_unknown_execution_is_idempotent():
    repository = InMemoryWorkflowRepository()

    repository.delete("unknown")

    assert repository.exists("unknown") is False


def test_list_all_returns_all_executions():
    repository = InMemoryWorkflowRepository()

    first = make_execution(
        execution_id="execution-001",
    )
    second = make_execution(
        execution_id="execution-002",
    )

    repository.save(first)
    repository.save(second)

    stored = repository.list_all()

    assert len(stored) == 2
    assert {
        execution.execution_id
        for execution in stored
    } == {
        "execution-001",
        "execution-002",
    }


def test_save_replaces_execution_with_same_id():
    repository = InMemoryWorkflowRepository()
    execution = make_execution()

    repository.save(execution)

    execution.metadata["version"] = 2
    repository.save(execution)

    stored = repository.get(execution.execution_id)

    assert stored is not None
    assert stored.metadata["version"] == 2
    assert len(repository.list_all()) == 1


def test_repository_copies_object_on_save():
    repository = InMemoryWorkflowRepository()
    execution = make_execution()

    repository.save(execution)

    execution.metadata["external-change"] = True

    stored = repository.get(execution.execution_id)

    assert stored is not None
    assert "external-change" not in stored.metadata


def test_repository_copies_object_on_get():
    repository = InMemoryWorkflowRepository()
    execution = make_execution()

    repository.save(execution)

    first_read = repository.get(execution.execution_id)

    assert first_read is not None

    first_read.metadata["mutated"] = True

    second_read = repository.get(execution.execution_id)

    assert second_read is not None
    assert "mutated" not in second_read.metadata


def test_repository_copies_nested_definition():
    repository = InMemoryWorkflowRepository()
    execution = make_execution()

    repository.save(execution)

    stored = repository.get(execution.execution_id)

    assert stored is not None

    stored.definition.steps[0].metadata["changed"] = True

    second_read = repository.get(execution.execution_id)

    assert second_read is not None
    assert "changed" not in second_read.definition.steps[0].metadata


def test_list_all_returns_copies():
    repository = InMemoryWorkflowRepository()
    execution = make_execution()

    repository.save(execution)

    executions = repository.list_all()
    executions[0].metadata["changed"] = True

    stored = repository.get(execution.execution_id)

    assert stored is not None
    assert "changed" not in stored.metadata
