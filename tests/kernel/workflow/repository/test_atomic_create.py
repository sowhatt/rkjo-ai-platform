from concurrent.futures import ThreadPoolExecutor
from rkjo_kernel.workflow.repository.memory import InMemoryWorkflowRepository
from rkjo_kernel.workflow.models.workflow_execution import WorkflowExecution
from rkjo_kernel.workflow.models.workflow_definition import WorkflowDefinition


def test_concurrent_creates_do_not_overwrite_owner():
    repository = InMemoryWorkflowRepository()
    def create(tenant):
        execution = WorkflowExecution(definition=WorkflowDefinition(workflow_id="test", name="Test", steps=[]), execution_id="same", metadata={"tenant_id": tenant})
        try:
            repository.create(execution)
            return tenant
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        winners = [result for result in pool.map(create, [f"tenant-{i}" for i in range(20)]) if result]
    assert len(winners) == 1
    assert repository.get("same").metadata["tenant_id"] == winners[0]
