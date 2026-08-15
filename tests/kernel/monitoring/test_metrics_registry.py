import pytest

from rkjo_kernel.monitoring.metrics import MetricsRegistry


def test_increment_metric():
    metrics = MetricsRegistry()

    metrics.increment(
        "workflow.created"
    )

    assert metrics.get(
        "workflow.created"
    ) == 1


def test_increment_metric_by_value():
    metrics = MetricsRegistry()

    metrics.increment(
        "workflow.created",
        3,
    )

    assert metrics.get(
        "workflow.created"
    ) == 3


def test_unknown_metric_returns_zero():
    metrics = MetricsRegistry()

    assert metrics.get(
        "unknown"
    ) == 0


def test_snapshot_returns_counters():
    metrics = MetricsRegistry()

    metrics.increment(
        "workflow.created"
    )

    metrics.increment(
        "runtime.success",
        2,
    )

    assert metrics.snapshot() == {
        "workflow.created": 1,
        "runtime.success": 2,
    }


def test_reset_clears_metrics():
    metrics = MetricsRegistry()

    metrics.increment(
        "workflow.created"
    )

    metrics.reset()

    assert metrics.snapshot() == {}


def test_empty_metric_name_is_rejected():
    metrics = MetricsRegistry()

    with pytest.raises(
        ValueError,
        match="Metric name",
    ):
        metrics.increment(" ")


def test_negative_increment_is_rejected():
    metrics = MetricsRegistry()

    with pytest.raises(
        ValueError,
        match="negative",
    ):
        metrics.increment(
            "workflow.created",
            -1,
        )
