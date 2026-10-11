"""OMNI-016.4.2: verify real FastAPI middleware and tenant-bound HTTP responses."""
from datetime import datetime, timezone
from types import SimpleNamespace

from rkjo_kernel.omnichannel.operations import QueueHealth


NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)


def mock_backend(monkeypatch):
    from rkjo_api import omnichannel

    class Operations:
        def __init__(self, url):
            pass
        def snapshot(self, *, tenant_id, now):
            return SimpleNamespace(
                inbound=QueueHealth(1,0,0),
                routes=QueueHealth(2,0,0),
                outbound=QueueHealth(3,0,0),
                uncertain_outbound=0,provider_confirmed_uncommitted=0,
                sent_without_binding=0,delivery_receipts=4,
            )
    class Monitor:
        def __init__(self, *, operations):
            pass
        def check(self, *, tenant_id, now):
            return SimpleNamespace(healthy=True,alerts=[])
    class Incidents:
        def __init__(self,url):
            pass
        def list(self, *, tenant_id, limit):
            return []
        def acknowledge(self, *, tenant_id, code, operator_id):
            return SimpleNamespace(code=code,status="acknowledged",
                                   acknowledged_by=operator_id)
    class Heartbeats:
        def __init__(self,url):
            pass
        def list(self, *, tenant_id, now):
            return []
    monkeypatch.setattr(omnichannel,"PostgreSQLOmnichannelWorkerHeartbeats",Heartbeats)
    monkeypatch.setattr(omnichannel,"PostgreSQLOmnichannelOperations",Operations)
    monkeypatch.setattr(omnichannel,"PostgreSQLOmnichannelMonitor",Monitor)
    monkeypatch.setattr(omnichannel,"PostgreSQLOmnichannelIncidents",Incidents)
    monkeypatch.setenv("RKJO_DATABASE_URL","postgresql://dummy")


def test_dashboard_requires_authentication(client):
    response=client.get("/omnichannel/dashboard")
    assert response.status_code==401


def test_dashboard_is_tenant_scoped_and_exposes_only_aggregates(client,monkeypatch):
    mock_backend(monkeypatch)
    response=client.get("/omnichannel/dashboard",headers={"X-API-Key":"rkjo-viewer-key"})
    assert response.status_code==200
    body=response.json()
    assert body["tenant_id"]=="tenant-a"
    assert body["queues"]["outbound"]["pending"]==3
    assert "access_token" not in str(body)
    assert "recipient_ref" not in str(body)


def test_viewer_cannot_acknowledge(client,monkeypatch):
    mock_backend(monkeypatch)
    response=client.post(
        "/omnichannel/incidents/OUTBOUND_FAILED/acknowledge",
        headers={"X-API-Key":"rkjo-viewer-key"},
    )
    assert response.status_code==403


def test_operator_can_acknowledge(client,monkeypatch):
    mock_backend(monkeypatch)
    response=client.post(
        "/omnichannel/incidents/OUTBOUND_FAILED/acknowledge",
        headers={"X-API-Key":"rkjo-operator-key"},
    )
    assert response.status_code==200
    assert response.json()["status"]=="acknowledged"


def test_unbound_identity_rejected_even_with_admin_key(client,monkeypatch):
    mock_backend(monkeypatch)
    monkeypatch.delenv("RKJO_ADMIN_TENANT_ID",raising=False)
    response=client.get("/omnichannel/dashboard",headers={"X-API-Key":"rkjo-admin-key"})
    assert response.status_code==403
