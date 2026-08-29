from unittest.mock import Mock

from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.registry.descriptor import AgentStatus
from rkjo_worker.workflow_result_consumer import (
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
