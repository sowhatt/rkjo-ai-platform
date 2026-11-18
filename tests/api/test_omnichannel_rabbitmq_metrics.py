"""OMNI-016.4.3.2: real RabbitMQ telemetry contracts, no live broker required."""
from io import BytesIO
import json

import pytest
from fastapi.testclient import TestClient

from rkjo_api.main import app
from rkjo_kernel.omnichannel.rabbitmq_telemetry import (
    RabbitMQQueueProbe, sanitized_snapshot,
)


class Response:
    status=200
    headers={"Content-Type":"application/json"}
    def __init__(self, body):
        self.body=body
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, amount):
        return self.body


def config():
    return dict(base_url="http://rabbitmq.local:15672",
                username="observer",password="secret",vhost="/",
                queue_names=["rkjo.omnichannel.agent","rkjo.omnichannel.agent.dlq"])


def test_probe_returns_ready_unacked_consumers_and_dlq(monkeypatch):
    import rkjo_kernel.omnichannel.rabbitmq_telemetry as module
    seen=[]
    def open_request(req,timeout):
        seen.append(req.full_url)
        name="rkjo.omnichannel.agent.dlq" if req.full_url.endswith(".dlq") else "rkjo.omnichannel.agent"
        return Response(json.dumps({
            "name":name,"messages_ready":3 if name.endswith(".dlq") else 5,
            "messages_unacknowledged":0 if name.endswith(".dlq") else 2,
            "messages":3 if name.endswith(".dlq") else 7,"consumers":0 if name.endswith(".dlq") else 1,
        }).encode())
    monkeypatch.setattr(module,"urlopen",open_request)
    data=RabbitMQQueueProbe(**config()).snapshot()
    assert data[0].ready==5
    assert data[0].unacked==2
    assert data[0].consumers==1
    assert sanitized_snapshot(data)["totals"]["dlq"]==3
    assert "%2F" in seen[0]


@pytest.mark.parametrize("queues", [[], ["x","x"], ["x/y"], [""]])
def test_no_implicit_or_unsafe_queue_discovery(queues):
    with pytest.raises(ValueError):
        RabbitMQQueueProbe(**(config()|{"queue_names":queues}))


def test_malformed_broker_counters_fail_closed(monkeypatch):
    import rkjo_kernel.omnichannel.rabbitmq_telemetry as module
    monkeypatch.setattr(module,"urlopen",lambda *a,**k: Response(
        json.dumps({"name":"rkjo.omnichannel.agent","messages_ready":4,
                    "messages_unacknowledged":0,"messages":1,"consumers":1}).encode()))
    with pytest.raises(RuntimeError):
        RabbitMQQueueProbe(**(config()|{"queue_names":["rkjo.omnichannel.agent"]})).snapshot()


def test_read_only_endpoint_blocks_viewer_and_operator():
    with TestClient(app) as client:
        for key in ["rkjo-viewer-key","rkjo-operator-key"]:
            response=client.get("/internal/omnichannel/rabbitmq",
                                headers={"X-API-Key":key})
            assert response.status_code==403
        assert client.get("/internal/omnichannel/rabbitmq").status_code==401


def test_admin_broker_failure_is_redacted(monkeypatch):
    # The test API key can be tenant-bound; an infrastructure admin is unbound.
    # Test broker failure only after the infrastructure authorization succeeds.
    import rkjo_api.omnichannel_internal as internal
    from rkjo_api.identity import AuthenticatedIdentity
    from rkjo_api.security import ApiRole
    monkeypatch.setattr(
        internal, "get_authenticated_identity",
        lambda request: AuthenticatedIdentity(
            subject="infra-admin", role=ApiRole.ADMIN, tenant_id=None,
        ),
    )
    monkeypatch.delenv("RKJO_OMNI_RABBITMQ_MONITORED_QUEUES",raising=False)
    with TestClient(app) as client:
        response=client.get("/internal/omnichannel/rabbitmq",
                            headers={"X-API-Key":"rkjo-admin-key"})
    assert response.status_code==503
    assert response.json()=={"detail":"Broker monitoring unavailable."}
