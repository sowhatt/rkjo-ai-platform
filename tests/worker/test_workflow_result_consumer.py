from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.registry.descriptor import AgentStatus
from rkjo_worker.workflow_result_consumer import (
    WorkflowResultConsumer,
    build_result_handler,
)


def test_result_consumer_bootstraps_routable_worker(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "RKJO_WORKER_AGENT_NAME",
        "rkjo.result.worker",
    )
    monkeypatch.setenv(
        "RKJO_WORKER_QUEUE",
        "rkjo.result.queue",
    )
    monkeypatch.setenv(
        "RKJO_WORKER_CAPABILITY",
        "platform_task",
    )
    monkeypatch.setenv(
        "RKJO_WORKFLOW_RESULT_QUEUE",
        "rkjo.workflow.results.test",
    )

    event_bus = Mock(
        spec=EventBus
    )

    result_queue, handler = build_result_handler(
        event_bus=event_bus,
    )

    descriptor = (
        handler.router.registry_service.get_agent(
            "rkjo.result.worker"
        )
    )

    assert result_queue == (
        "rkjo.workflow.results.test"
    )
    assert descriptor is not None
    assert descriptor.status == AgentStatus.AVAILABLE
    assert descriptor.queue_name == "rkjo.result.queue"
    assert descriptor.has_capability(
        "platform_task"
    )


def test_consumer_rebuilds_bus_and_handler_after_failure() -> None:
    first_bus = Mock(
        spec=EventBus
    )
    second_bus = Mock(
        spec=EventBus
    )

    first_bus.consume_agent_messages.side_effect = (
        RuntimeError("broker unavailable")
    )
    second_bus.consume_agent_messages.return_value = None

    event_bus_factory = Mock(
        side_effect=[
            first_bus,
            second_bus,
        ]
    )

    first_handler = SimpleNamespace(
        handle=Mock()
    )
    second_handler = SimpleNamespace(
        handle=Mock()
    )

    handler_builder = Mock(
        side_effect=[
            (
                "rkjo.workflow.results",
                first_handler,
            ),
            (
                "rkjo.workflow.results",
                second_handler,
            ),
        ]
    )

    sleep_fn = Mock()

    consumer = WorkflowResultConsumer(
        event_bus_factory=event_bus_factory,
        handler_builder=handler_builder,
        sleep_fn=sleep_fn,
    )

    consumer.run()

    assert event_bus_factory.call_count == 2
    assert handler_builder.call_count == 2

    sleep_fn.assert_called_once_with(
        1.0
    )

    first_bus.close.assert_called_once_with()
    second_bus.close.assert_called_once_with()

    second_bus.consume_agent_messages.assert_called_once_with(
        queue_name="rkjo.workflow.results",
        callback=second_handler.handle,
    )


def test_consumer_uses_bounded_exponential_backoff() -> None:
    buses = [
        Mock(spec=EventBus)
        for _ in range(4)
    ]

    for bus in buses[:3]:
        bus.consume_agent_messages.side_effect = (
            RuntimeError("broker unavailable")
        )

    buses[3].consume_agent_messages.return_value = None

    event_bus_factory = Mock(
        side_effect=buses
    )

    handlers = [
        SimpleNamespace(
            handle=Mock()
        )
        for _ in range(4)
    ]

    handler_builder = Mock(
        side_effect=[
            (
                "rkjo.workflow.results",
                handler,
            )
            for handler in handlers
        ]
    )

    sleep_fn = Mock()

    consumer = WorkflowResultConsumer(
        event_bus_factory=event_bus_factory,
        handler_builder=handler_builder,
        retry_initial_seconds=1.0,
        retry_max_seconds=3.0,
        retry_multiplier=2.0,
        sleep_fn=sleep_fn,
    )

    consumer.run()

    assert [
        call.args[0]
        for call in sleep_fn.call_args_list
    ] == [
        1.0,
        2.0,
        3.0,
    ]

    assert event_bus_factory.call_count == 4
    assert handler_builder.call_count == 4

    for bus in buses:
        bus.close.assert_called_once_with()


@pytest.mark.parametrize(
    (
        "kwargs",
        "message",
    ),
    [
        (
            {
                "retry_initial_seconds": 0,
            },
            "retry_initial_seconds",
        ),
        (
            {
                "retry_initial_seconds": 2,
                "retry_max_seconds": 1,
            },
            "retry_max_seconds",
        ),
        (
            {
                "retry_multiplier": 0.5,
            },
            "retry_multiplier",
        ),
    ],
)
def test_consumer_rejects_invalid_retry_configuration(
    kwargs,
    message,
) -> None:
    with pytest.raises(
        ValueError,
        match=message,
    ):
        WorkflowResultConsumer(
            event_bus_factory=Mock(),
            **kwargs,
        )


def test_result_consumer_marks_ready_before_consuming() -> None:
    from rkjo_worker.health import WorkerHealth

    health = WorkerHealth(
        service_name="workflow-result-consumer"
    )

    class Handler:
        def handle(self, message):
            return None

    class EventBus:
        def consume_agent_messages(
            self,
            *,
            queue_name,
            callback,
        ):
            snapshot = health.snapshot()

            assert snapshot.live is True
            assert snapshot.ready is True
            assert snapshot.status == "ready"

        def close(self):
            return None

    consumer = WorkflowResultConsumer(
        event_bus_factory=EventBus,
        handler_builder=lambda *, event_bus: (
            "workflow-results",
            Handler(),
        ),
        health=health,
    )

    consumer.run()

    snapshot = health.snapshot()

    assert snapshot.live is True
    assert snapshot.ready is True


def test_result_consumer_marks_not_ready_on_failure() -> None:
    from rkjo_worker.health import WorkerHealth

    health = WorkerHealth(
        service_name="workflow-result-consumer"
    )

    class Handler:
        def handle(self, message):
            return None

    class EventBus:
        def consume_agent_messages(
            self,
            *,
            queue_name,
            callback,
        ):
            raise RuntimeError(
                "RabbitMQ unavailable"
            )

        def close(self):
            return None

    def stop_after_failure(_delay):
        consumer.stop()

    consumer = WorkflowResultConsumer(
        event_bus_factory=EventBus,
        handler_builder=lambda *, event_bus: (
            "workflow-results",
            Handler(),
        ),
        health=health,
        sleep_fn=stop_after_failure,
    )

    consumer.run()

    snapshot = health.snapshot()

    assert snapshot.live is False
    assert snapshot.ready is False
    assert snapshot.status == "stopped"
    assert snapshot.last_error == (
        "RabbitMQ unavailable"
    )


def test_result_consumer_recovers_readiness_after_retry() -> None:
    from rkjo_worker.health import WorkerHealth

    health = WorkerHealth(
        service_name="workflow-result-consumer"
    )

    attempts = {"count": 0}

    class Handler:
        def handle(self, message):
            return None

    class EventBus:
        def consume_agent_messages(
            self,
            *,
            queue_name,
            callback,
        ):
            attempts["count"] += 1

            if attempts["count"] == 1:
                raise RuntimeError(
                    "temporary RabbitMQ failure"
                )

        def close(self):
            return None

    consumer = WorkflowResultConsumer(
        event_bus_factory=EventBus,
        handler_builder=lambda *, event_bus: (
            "workflow-results",
            Handler(),
        ),
        health=health,
        sleep_fn=lambda _delay: None,
    )

    consumer.run()

    snapshot = health.snapshot()

    assert attempts["count"] == 2
    assert snapshot.live is True
    assert snapshot.ready is True
    assert snapshot.status == "ready"
    assert snapshot.last_error is None


def test_result_consumer_marks_stopped_on_keyboard_interrupt() -> None:
    from rkjo_worker.health import WorkerHealth

    health = WorkerHealth(
        service_name="workflow-result-consumer"
    )

    class Handler:
        def handle(self, message):
            return None

    class EventBus:
        def consume_agent_messages(
            self,
            *,
            queue_name,
            callback,
        ):
            raise KeyboardInterrupt

        def close(self):
            return None

    consumer = WorkflowResultConsumer(
        event_bus_factory=EventBus,
        handler_builder=lambda *, event_bus: (
            "workflow-results",
            Handler(),
        ),
        health=health,
    )

    consumer.run()

    snapshot = health.snapshot()

    assert snapshot.live is False
    assert snapshot.ready is False
    assert snapshot.status == "stopped"
