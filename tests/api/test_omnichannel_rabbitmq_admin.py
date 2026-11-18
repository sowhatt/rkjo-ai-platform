"""OMNI-016.4.3.3: infrastructure admin scope and alert response."""
from fastapi.testclient import TestClient

from rkjo_api.main import app
from rkjo_kernel.omnichannel.rabbitmq_telemetry import QueueTelemetry


def test_tenant_bound_admin_cannot_access_global_broker(monkeypatch):
    import rkjo_api.omnichannel_internal as module
    from rkjo_api.identity import AuthenticatedIdentity
    from rkjo_api.security import ApiRole
    monkeypatch.setattr(
        module, "get_authenticated_identity",
        lambda request: AuthenticatedIdentity(
            subject="tenant-admin", role=ApiRole.ADMIN, tenant_id="tenant-a",
        ),
    )
    with TestClient(app) as client:
        response = client.get(
            "/internal/omnichannel/rabbitmq",
            headers={"X-API-Key":"rkjo-admin-key"},
        )
    assert response.status_code == 403


def test_infrastructure_admin_receives_dlq_alerts(monkeypatch):
    import rkjo_api.omnichannel_internal as module
    from rkjo_api.identity import AuthenticatedIdentity
    from rkjo_api.security import ApiRole
    monkeypatch.setattr(module, "get_authenticated_identity",
        lambda request: AuthenticatedIdentity(subject="infra-admin",role=ApiRole.ADMIN))
    class Probe:
        def __init__(self, **kwargs):
            pass
        def snapshot(self):
            return (QueueTelemetry("agent.dlq",1,0,0,1,True),)
    monkeypatch.setattr(module, "RabbitMQQueueProbe", Probe)
    config = {
        "RKJO_OMNI_RABBITMQ_MONITORED_QUEUES":"agent.dlq",
        "RKJO_OMNI_RABBITMQ_MANAGEMENT_URL":"http://localhost:15672",
        "RKJO_OMNI_RABBITMQ_MONITOR_USER":"observer",
        "RKJO_OMNI_RABBITMQ_MONITOR_PASSWORD":"test-secret",
    }
    for name,value in config.items():
        monkeypatch.setenv(name,value)
    with TestClient(app) as client:
        response = client.get("/internal/omnichannel/rabbitmq",
                              headers={"X-API-Key":"rkjo-admin-key"})
    assert response.status_code == 200
    payload=response.json()
    assert payload["healthy"] is False
    assert payload["scope"] == "infrastructure"
    assert payload["alerts"][0]["code"] == "DLQ_NONEMPTY"
    assert payload["totals"]["dlq"] == 1
    assert "test-secret" not in response.text
