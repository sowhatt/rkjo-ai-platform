import pytest

from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.orchestrator.orchestrator import (
    AgentOrchestrator,
    MissionRequest,
    NoSuitableAgentError,
)
from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.registry.discovery import AgentDiscovery
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.services.registry_service import RegistryService


class FakeEventBus:
    """
    Bus en mémoire utilisé pour tester l'Orchestrator
    sans dépendre de RabbitMQ.
    """

    def __init__(self) -> None:
        self.published_messages: list[
            tuple[str, AgentMessage]
        ] = []

    def publish_agent_message(
        self,
        queue_name: str,
        message: AgentMessage,
    ) -> None:
        self.published_messages.append(
            (queue_name, message)
        )

    def publish(
        self,
        queue_name: str,
        message: str,
    ) -> None:
        raise NotImplementedError

    def consume(
        self,
        queue_name: str,
        callback,
    ) -> None:
        raise NotImplementedError

    def consume_agent_messages(
        self,
        queue_name: str,
        callback,
    ) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass


def create_orchestrator():
    """
    Construit l'Orchestrator et ses dépendances de test.
    """

    registry = AgentRegistry()
    registry_service = RegistryService(registry)
    discovery = AgentDiscovery(registry_service)
    event_bus = FakeEventBus()

    orchestrator = AgentOrchestrator(
        discovery=discovery,
        event_bus=event_bus,
    )

    return registry_service, event_bus, orchestrator


def create_climate_agent() -> AgentDescriptor:
    """
    Crée un Agent Climat disponible pour les tests.
    """

    return AgentDescriptor(
        name="adip.climate_agent",
        display_name="ADIP Climate Agent",
        product="ADIP",
        queue_name="adip.climate",
        status=AgentStatus.AVAILABLE,
        priority=8,
        supported_regions=["france"],
        supported_languages=["fr"],
        capabilities=[
            AgentCapability(
                name="drought_analysis",
                description="Analyse les risques de sécheresse.",
                confidence_score=0.9,
                estimated_cost=2,
                average_duration_ms=1000,
            )
        ],
    )


def test_orchestrator_discovers_and_dispatches_agent():
    """
    Vérifie la chaîne mission → découverte → AgentMessage → EventBus.
    """

    service, event_bus, orchestrator = create_orchestrator()

    service.register_agent(
        create_climate_agent()
    )

    request = MissionRequest(
        capability_name="drought_analysis",
        product="ADIP",
        region="france",
        language="fr",
        priority=7,
        payload={
            "question": (
                "Analyse le risque de sécheresse "
                "pour le blé dans l'Eure."
            ),
            "department_code": "27",
            "crop": "blé tendre",
        },
    )

    result = orchestrator.dispatch(request)

    assert result.discovery.agent.name == "adip.climate_agent"
    assert result.queue_name == "adip.climate"
    assert result.message.target == "adip.climate_agent"
    assert result.message.priority == 7
    assert result.message.correlation_id == request.correlation_id
    assert result.message.metadata["product"] == "ADIP"
    assert len(event_bus.published_messages) == 1

    queue_name, published_message = (
        event_bus.published_messages[0]
    )

    assert queue_name == "adip.climate"
    assert published_message.message_id == result.message.message_id


def test_orchestrator_rejects_unknown_capability():
    """
    Vérifie qu'aucune mission n'est envoyée sans agent compatible.
    """

    _, event_bus, orchestrator = create_orchestrator()

    request = MissionRequest(
        capability_name="soil_analysis",
        payload={
            "question": "Analyse le sol."
        },
    )

    with pytest.raises(
        NoSuitableAgentError
    ):
        orchestrator.dispatch(request)

    assert event_bus.published_messages == []


def test_orchestrator_respects_region_filter():
    """
    Vérifie que les contraintes géographiques sont respectées.
    """

    service, event_bus, orchestrator = create_orchestrator()

    service.register_agent(
        create_climate_agent()
    )

    request = MissionRequest(
        capability_name="drought_analysis",
        region="canada",
        payload={
            "question": "Analyse le risque climatique."
        },
    )

    with pytest.raises(
        NoSuitableAgentError
    ):
        orchestrator.dispatch(request)

    assert event_bus.published_messages == []

def test_orchestrator_plan_selects_agent_without_publishing():
    service, event_bus, orchestrator = create_orchestrator()

    service.register_agent(
        create_climate_agent()
    )

    request = MissionRequest(
        capability_name="drought_analysis",
        product="ADIP",
        region="france",
        language="fr",
        priority=7,
        correlation_id="CORR-PLAN-001",
        payload={
            "department_code": "27",
            "crop": "blé tendre",
        },
    )

    plan = orchestrator.plan(request)

    assert plan.discovery.agent.name == (
        "adip.climate_agent"
    )
    assert plan.queue_name == "adip.climate"
    assert plan.message.target == (
        "adip.climate_agent"
    )
    assert plan.message.priority == 7
    assert plan.message.correlation_id == (
        "CORR-PLAN-001"
    )
    assert plan.message.metadata[
        "requested_capability"
    ] == "drought_analysis"

    assert event_bus.published_messages == []


def test_orchestrator_dispatch_uses_prepared_plan():
    service, event_bus, orchestrator = create_orchestrator()

    service.register_agent(
        create_climate_agent()
    )

    request = MissionRequest(
        capability_name="drought_analysis",
        product="ADIP",
        region="france",
        payload={
            "department_code": "27",
        },
    )

    result = orchestrator.dispatch(request)

    assert len(event_bus.published_messages) == 1

    queue_name, message = (
        event_bus.published_messages[0]
    )

    assert queue_name == result.queue_name
    assert message is result.message
    assert result.discovery.agent.name == (
        "adip.climate_agent"
    )
