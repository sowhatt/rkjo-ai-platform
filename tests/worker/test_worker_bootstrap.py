from unittest.mock import Mock

from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.registry.descriptor import AgentStatus
from rkjo_kernel.registry.discovery import AgentDiscovery, DiscoveryCriteria
from rkjo_worker.main import PlatformWorkerAgent, build_runtime


class FakeEventBus:
    def publish(self, *args, **kwargs):
        pass

    def consume(self, *args, **kwargs):
        pass

    def publish_agent_message(
        self,
        *args,
        **kwargs,
    ):
        pass

    def consume_agent_messages(
        self,
        *args,
        **kwargs,
    ):
        pass

    def close(self):
        pass


def test_platform_worker_processes_message():
    agent = PlatformWorkerAgent(
        agent_name="rkjo.platform.worker",
        queue_name="rkjo.platform.worker",
        event_bus=FakeEventBus(),
    )

    message = AgentMessage(
        source="test",
        target="rkjo.platform.worker",
        payload={
            "hello": "world",
        },
    )

    result = agent.process(
        message
    )

    assert result["processed_by"] == (
        "rkjo.platform.worker"
    )

    assert result["payload"] == {
        "hello": "world"
    }


def test_worker_registers_discoverable_capability(monkeypatch):
    monkeypatch.setenv(
        "RKJO_WORKER_AGENT_NAME",
        "rkjo.test.worker",
    )
    monkeypatch.setenv(
        "RKJO_WORKER_QUEUE",
        "rkjo.test.worker.queue",
    )
    monkeypatch.setenv(
        "RKJO_WORKER_CAPABILITY",
        "document_analysis",
    )

    bus = Mock(spec=EventBus)
    runtime = build_runtime(event_bus=bus)

    descriptor = runtime.registry_service.get_agent(
        "rkjo.test.worker"
    )

    assert descriptor is not None
    assert descriptor.queue_name == "rkjo.test.worker.queue"
    assert descriptor.has_capability("document_analysis")

    runtime.registry_service.update_agent_status(
        agent_name=descriptor.name,
        status=AgentStatus.AVAILABLE,
    )

    discovery = AgentDiscovery(
        registry_service=runtime.registry_service
    )

    result = discovery.discover(
        DiscoveryCriteria(
            capability_name="document_analysis"
        )
    )

    assert result is not None
    assert result.agent.name == "rkjo.test.worker"
    assert result.agent.queue_name == "rkjo.test.worker.queue"
    assert result.capability.name == "document_analysis"


def test_main_starts_health_server_and_closes_bus(monkeypatch):
    from rkjo_kernel.runtime.status import RuntimeStatus
    from rkjo_worker import main as worker_main

    bus = Mock(spec=EventBus)

    runtime = Mock()
    runtime.status = RuntimeStatus.CREATED
    runtime.last_error = None
    runtime.event_bus = bus

    def start_runtime():
        runtime.status = RuntimeStatus.RUNNING

    runtime.start.side_effect = start_runtime

    health_server = Mock()

    monkeypatch.setattr(
        worker_main,
        "build_runtime",
        lambda: runtime,
    )
    monkeypatch.setattr(
        worker_main,
        "HealthHTTPServer",
        lambda **kwargs: health_server,
    )
    monkeypatch.setattr(
        worker_main.signal,
        "signal",
        Mock(),
    )

    worker_main.main()

    health_server.start.assert_called_once_with()
    runtime.start.assert_called_once_with()
    health_server.stop.assert_called_once_with()
    bus.close.assert_called_once_with()


def test_main_handles_keyboard_interrupt(monkeypatch):
    from rkjo_kernel.runtime.status import RuntimeStatus
    from rkjo_worker import main as worker_main

    bus = Mock(spec=EventBus)

    runtime = Mock()
    runtime.status = RuntimeStatus.RUNNING
    runtime.last_error = None
    runtime.event_bus = bus
    runtime.start.side_effect = KeyboardInterrupt

    health_server = Mock()

    monkeypatch.setattr(
        worker_main,
        "build_runtime",
        lambda: runtime,
    )
    monkeypatch.setattr(
        worker_main,
        "HealthHTTPServer",
        lambda **kwargs: health_server,
    )
    monkeypatch.setattr(
        worker_main.signal,
        "signal",
        Mock(),
    )

    worker_main.main()

    health_server.start.assert_called_once_with()
    health_server.stop.assert_called_once_with()
    bus.close.assert_called_once_with()
