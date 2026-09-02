import pytest

from rkjo_worker.health import WorkerHealth


def test_worker_health_starts_live_but_not_ready() -> None:
    health = WorkerHealth(
        service_name="workflow-result-consumer"
    )

    snapshot = health.snapshot()

    assert snapshot.service_name == (
        "workflow-result-consumer"
    )
    assert snapshot.live is True
    assert snapshot.ready is False
    assert snapshot.status == "not_ready"
    assert snapshot.last_error is None


def test_worker_health_can_become_ready() -> None:
    health = WorkerHealth(
        service_name="outbox-worker"
    )

    health.mark_ready()

    snapshot = health.snapshot()

    assert snapshot.live is True
    assert snapshot.ready is True
    assert snapshot.status == "ready"
    assert snapshot.last_error is None


def test_worker_health_records_dependency_failure() -> None:
    health = WorkerHealth(
        service_name="outbox-worker"
    )
    health.mark_ready()

    health.mark_not_ready(
        RuntimeError("RabbitMQ unavailable")
    )

    snapshot = health.snapshot()

    assert snapshot.live is True
    assert snapshot.ready is False
    assert snapshot.status == "not_ready"
    assert snapshot.last_error == (
        "RabbitMQ unavailable"
    )


def test_worker_health_can_be_stopped() -> None:
    health = WorkerHealth(
        service_name="workflow-result-consumer"
    )
    health.mark_ready()

    health.mark_stopped()

    snapshot = health.snapshot()

    assert snapshot.live is False
    assert snapshot.ready is False
    assert snapshot.status == "stopped"


def test_worker_health_rejects_empty_service_name() -> None:
    with pytest.raises(
        ValueError,
        match="service_name must not be empty",
    ):
        WorkerHealth(service_name="   ")


def test_snapshot_can_be_serialized() -> None:
    health = WorkerHealth(
        service_name="outbox-worker"
    )
    health.mark_ready()

    assert health.snapshot().as_dict() == {
        "service_name": "outbox-worker",
        "live": True,
        "ready": True,
        "status": "ready",
        "last_error": None,
    }


def test_stopped_worker_cannot_become_ready_again() -> None:
    health = WorkerHealth(
        service_name="test-worker"
    )

    health.mark_ready()
    health.mark_stopped()
    health.mark_ready()

    snapshot = health.snapshot()

    assert snapshot.live is False
    assert snapshot.ready is False
    assert snapshot.status == "stopped"
