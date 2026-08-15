from rkjo_worker.main import PlatformWorkerAgent


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
    from rkjo_kernel.messages.agent_message import (
        AgentMessage,
    )

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
