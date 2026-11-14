import pytest
from fastapi.testclient import TestClient
from rkjo_api.main import app
from rkjo_api.dependencies import get_workflow_engine, get_async_dispatcher, get_workflow_agent_router, get_workflow_uow_factory
from rkjo_kernel.workflow.engine import WorkflowEngine
from rkjo_kernel.workflow.repository.memory import InMemoryWorkflowRepository

PAYLOAD = {"workflow_id": "tenant-test", "name": "Tenant test", "execution_id": "shared-id",
           "steps": [{"step_id": "one", "name": "One", "agent_name": "example.agent"}]}
HEADERS = {"X-API-Key": "rkjo-test-api-key"}


@pytest.fixture
def setup():
    repository = InMemoryWorkflowRepository()
    engine = WorkflowEngine(repository=repository)
    from rkjo_kernel.workflow.in_memory_unit_of_work import InMemoryWorkflowUnitOfWork
    uow = InMemoryWorkflowUnitOfWork()
    uow.workflows = repository
    class NeverDispatch:
        def dispatch(self, **kwargs):
            pytest.fail("Unauthorized request reached dispatcher")
    overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_workflow_uow_factory] = lambda: lambda: uow
    app.dependency_overrides[get_workflow_engine] = lambda: engine
    app.dependency_overrides[get_async_dispatcher] = NeverDispatch
    app.dependency_overrides[get_workflow_agent_router] = lambda: None
    try:
        with TestClient(app, headers=HEADERS) as client:
            yield client, repository
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides)


def test_create_binds_tenant_and_preserves_it_in_context(setup):
    client, repo = setup
    assert client.post('/workflows/executions', json=PAYLOAD).status_code == 201
    stored = repo.get('shared-id')
    assert stored.metadata['tenant_id'] == stored.context.metadata['tenant_id'] == 'tenant-a'
    assert client.get('/workflows/executions/shared-id').status_code == 200


def test_forged_tenant_is_rejected_before_save(setup):
    client, repo = setup
    assert client.post('/workflows/executions', json={**PAYLOAD, 'metadata': {'tenant_id': 'tenant-b'}}).status_code == 403
    assert repo.list_all() == []


def test_cross_tenant_read_start_and_overwrite_are_denied(setup, monkeypatch):
    client, repo = setup
    assert client.post('/workflows/executions', json=PAYLOAD).status_code == 201
    monkeypatch.setenv('RKJO_API_TENANT_ID', 'tenant-b')
    assert client.get('/workflows/executions/shared-id').status_code == 404
    assert client.post('/workflows/executions/shared-id/start').status_code == 404
    assert client.post('/workflows/executions', json=PAYLOAD).status_code == 422
    stored = repo.get('shared-id')
    assert stored.metadata['tenant_id'] == 'tenant-a'
    assert stored.status.value == 'pending'


@pytest.mark.parametrize('method,path', [('get','/workflows/executions/shared-id'), ('post','/workflows/executions/shared-id/start'), ('post','/workflows/executions')])
def test_unbound_admin_is_denied(setup, monkeypatch, method, path):
    client, repo = setup
    monkeypatch.delenv('RKJO_API_TENANT_ID')
    response = client.request(method, path, json=PAYLOAD if path.endswith('executions') else None)
    assert response.status_code == 403
    assert repo.list_all() == []


def test_legacy_unbound_execution_is_not_exposed(setup):
    client, repo = setup
    client.post('/workflows/executions', json=PAYLOAD)
    stored = repo.get('shared-id')
    stored.metadata.clear()
    stored.context.metadata.clear()
    repo.save(stored)
    assert client.get('/workflows/executions/shared-id').status_code == 404
    assert client.post('/workflows/executions/shared-id/start').status_code == 404
