import pytest
from fastapi.testclient import TestClient

from rkjo_api.dependencies import get_metrics_registry
from rkjo_api.main import app
from rkjo_kernel.monitoring.metrics import MetricsRegistry


@pytest.fixture
def metrics_registry():
    registry = MetricsRegistry()

    registry.increment(
        "workflow.created",
        2,
    )

    registry.increment(
        "runtime.success",
        3,
    )

    return registry


@pytest.fixture
def client(metrics_registry):
    def override_metrics():
        return metrics_registry

    app.dependency_overrides[
        get_metrics_registry
    ] = override_metrics

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(
        get_metrics_registry,
        None,
    )


def test_metrics_endpoint(
    client,
):
    response = client.get(
        "/metrics"
    )

    assert response.status_code == 200

    assert response.json() == {
        "counters": {
            "workflow.created": 2,
            "runtime.success": 3,
        }
    }
