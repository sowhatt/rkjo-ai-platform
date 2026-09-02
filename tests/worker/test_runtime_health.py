from types import SimpleNamespace

import pytest

from rkjo_kernel.runtime.status import RuntimeStatus
from rkjo_worker.runtime_health import RuntimeHealthAdapter


@pytest.mark.parametrize(
    (
        "runtime_status",
        "expected_live",
        "expected_ready",
        "expected_status",
    ),
    [
        (
            RuntimeStatus.CREATED,
            True,
            False,
            "not_ready",
        ),
        (
            RuntimeStatus.STARTING,
            True,
            False,
            "not_ready",
        ),
        (
            RuntimeStatus.RUNNING,
            True,
            True,
            "ready",
        ),
        (
            RuntimeStatus.ERROR,
            True,
            False,
            "not_ready",
        ),
        (
            RuntimeStatus.STOPPING,
            True,
            False,
            "not_ready",
        ),
        (
            RuntimeStatus.STOPPED,
            False,
            False,
            "stopped",
        ),
    ],
)
def test_runtime_health_maps_runtime_status(
    runtime_status,
    expected_live,
    expected_ready,
    expected_status,
):
    runtime = SimpleNamespace(
        status=runtime_status,
        last_error=None,
    )

    health = RuntimeHealthAdapter(runtime)

    snapshot = health.snapshot()

    assert snapshot.service_name == "platform-worker"
    assert snapshot.live is expected_live
    assert snapshot.ready is expected_ready
    assert snapshot.status == expected_status


def test_runtime_health_exposes_runtime_error():
    runtime = SimpleNamespace(
        status=RuntimeStatus.ERROR,
        last_error="RabbitMQ unavailable",
    )

    health = RuntimeHealthAdapter(runtime)

    snapshot = health.snapshot()

    assert snapshot.live is True
    assert snapshot.ready is False
    assert snapshot.status == "not_ready"
    assert snapshot.last_error == "RabbitMQ unavailable"


def test_runtime_health_rejects_empty_service_name():
    runtime = SimpleNamespace(
        status=RuntimeStatus.CREATED,
        last_error=None,
    )

    with pytest.raises(
        ValueError,
        match="service_name must not be empty",
    ):
        RuntimeHealthAdapter(
            runtime,
            service_name=" ",
        )
