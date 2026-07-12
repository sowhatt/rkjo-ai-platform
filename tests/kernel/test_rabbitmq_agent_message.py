from rkjo_kernel.events.rabbitmq_event_bus import RabbitMQEventBus
from rkjo_kernel.messages.agent_message import AgentMessage


def test_publish_agent_message_to_rabbitmq():
    """
    Vérifie qu'une mission structurée AgentMessage peut être envoyée
    réellement depuis le RKJO AI Kernel vers RabbitMQ.

    Pourquoi ce test ?

    Il valide notre première vraie chaîne multi-agent :

    RKJO Orchestrator
            ↓
    AgentMessage
            ↓
    RabbitMQEventBus
            ↓
    RabbitMQ
            ↓
    Queue adip.climate
    """

    # Création d'une vraie mission ADIP destinée au futur Agent Climat.
    message = AgentMessage(
        source="rkjo.orchestrator",
        target="adip.climate_agent",
        message_type="mission",
        priority=7,
        payload={
            "question": (
                "Analyse le risque de sécheresse "
                "pour le blé dans l'Eure"
            ),
            "territory": {
                "country": "France",
                "department": "Eure",
                "department_code": "27",
            },
            "crop": "blé tendre",
        },
        metadata={
            "product": "ADIP",
            "language": "fr",
            "test": True,
        },
    )

    # Connexion réelle à RabbitMQ.
    event_bus = RabbitMQEventBus()

    try:
        # Envoi de la mission structurée.
        event_bus.publish_agent_message(
            queue_name="adip.climate",
            message=message,
        )

    finally:
        # La connexion doit toujours être fermée,
        # même si une erreur survient pendant la publication.
        event_bus.close()

    # Si nous arrivons ici sans exception,
    # la publication technique a réussi.
    assert True