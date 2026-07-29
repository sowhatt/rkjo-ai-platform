from typing import Any

from rkjo_kernel.agents.base_agent import BaseAgent
from rkjo_kernel.messages.agent_message import AgentMessage


class FakeEventBus:
    """
    Faux EventBus utilisé pour tester BaseAgent sans RabbitMQ.

    Pourquoi ?

    Un test unitaire ne doit pas dépendre d'un service externe.
    RabbitMQ sera testé séparément dans les tests d'intégration.
    """

    def consume_agent_messages(
        self,
        queue_name: str,
        callback,
    ) -> None:
        self.queue_name = queue_name
        self.callback = callback

    def close(self) -> None:
        self.closed = True


class DemoAgent(BaseAgent):
    """
    Agent minimal utilisé uniquement pour tester BaseAgent.
    """

    def process(
        self,
        message: AgentMessage,
    ) -> Any:
        return {
            "received_question": message.payload["question"],
            "status": "processed",
        }


def test_base_agent_process_message():
    """
    Vérifie qu'un agent peut traiter un AgentMessage
    et mettre à jour ses statistiques.
    """

    event_bus = FakeEventBus()

    agent = DemoAgent(
        agent_name="adip.demo_agent",
        queue_name="adip.demo",
        event_bus=event_bus,
    )

    message = AgentMessage(
        source="rkjo.orchestrator",
        target="adip.demo_agent",
        payload={
            "question": "Analyse le risque agricole."
        },
    )

    assert agent.health()["processed_messages"] == 0
    assert agent.health()["failed_messages"] == 0

    result = agent._handle_message(message)

    assert result == {
        "received_question": "Analyse le risque agricole.",
        "status": "processed",
    }

    health = agent.health()

    assert health["processed_messages"] == 1
    assert health["failed_messages"] == 0
    assert health["status"] == "stopped"


def test_base_agent_rejects_wrong_target():
    """
    Vérifie qu'un agent refuse un message destiné
    à un autre agent.
    """

    event_bus = FakeEventBus()

    agent = DemoAgent(
        agent_name="adip.demo_agent",
        queue_name="adip.demo",
        event_bus=event_bus,
    )

    message = AgentMessage(
        source="rkjo.orchestrator",
        target="adip.other_agent",
        payload={
            "question": "Message mal routé."
        },
    )

    try:
        agent._handle_message(message)

    except ValueError:
        pass

    else:
        raise AssertionError(
            "The agent should reject a message "
            "intended for another target."
        )