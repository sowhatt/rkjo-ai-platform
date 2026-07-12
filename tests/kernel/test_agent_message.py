from rkjo_kernel.messages.agent_message import AgentMessage


def test_agent_message_creation():
    """
    Vérifie qu'un message entre agents est correctement créé.

    Pourquoi ce test ?

    Avant de connecter l'orchestrateur, RabbitMQ et les vrais agents ADIP,
    nous devons garantir que tous les composants utilisent le même format
    de message.
    """

    # Création d'une mission fictive envoyée par l'orchestrateur
    # au futur Agent Climat d'ADIP.
    message = AgentMessage(
        source="rkjo.orchestrator",
        target="adip.climate_agent",
        message_type="mission",
        priority=7,
        payload={
            "question": (
                "Analyse le risque de sécheresse "
                "pour le blé dans l'Eure"
            )
        },
    )

    # Vérifie que Pydantic a automatiquement créé un identifiant unique.
    assert message.message_id is not None

    # Vérifie que la décision possède également un correlation_id.
    #
    # Pourquoi ?
    # Plusieurs messages pourront appartenir à la même analyse :
    #
    # Orchestrateur
    #      ↓
    # Agent Climat
    # Agent Sol
    # Agent Eau
    #      ↓
    # Agent Vérification
    #
    # Tous pourront partager le même correlation_id.
    assert message.correlation_id is not None

    # Vérifie l'expéditeur.
    assert message.source == "rkjo.orchestrator"

    # Vérifie le destinataire.
    assert message.target == "adip.climate_agent"

    # Vérifie la priorité.
    assert message.priority == 7

    # Vérifie le contenu métier.
    assert (
        message.payload["question"]
        == "Analyse le risque de sécheresse pour le blé dans l'Eure"
    )