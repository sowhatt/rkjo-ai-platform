import pytest

from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.registry.registry import AgentRegistry


def create_climate_agent(
    priority: int = 8,
    status: AgentStatus = AgentStatus.AVAILABLE,
) -> AgentDescriptor:
    """
    Fabrique un Agent Climat de test.
    """

    return AgentDescriptor(
        name="adip.climate_agent",
        display_name="ADIP Climate Agent",
        product="ADIP",
        queue_name="adip.climate",
        status=status,
        priority=priority,
        capabilities=[
            AgentCapability(
                name="drought_analysis",
                description=(
                    "Analyse du risque de sécheresse."
                ),
                confidence_score=0.9,
            ),
            AgentCapability(
                name="weather_analysis",
                description=(
                    "Analyse météorologique."
                ),
                confidence_score=0.85,
            ),
        ],
    )


def create_backup_climate_agent() -> AgentDescriptor:
    """
    Fabrique un second agent proposant la même capacité,
    avec une priorité plus faible.
    """

    return AgentDescriptor(
        name="adip.backup_climate_agent",
        display_name="Backup Climate Agent",
        product="ADIP",
        queue_name="adip.climate.backup",
        status=AgentStatus.AVAILABLE,
        priority=4,
        capabilities=[
            AgentCapability(
                name="drought_analysis",
                description=(
                    "Analyse secondaire de sécheresse."
                ),
                confidence_score=0.75,
            )
        ],
    )


def test_register_and_find_agent():
    """
    Vérifie l'enregistrement et la recherche par nom.
    """

    registry = AgentRegistry()
    agent = create_climate_agent()

    registry.register(agent)

    result = registry.find_by_name(
        "adip.climate_agent"
    )

    assert result is not None
    assert result.name == "adip.climate_agent"
    assert registry.count() == 1


def test_register_replaces_existing_agent():
    """
    Vérifie qu'un nouvel enregistrement remplace
    la version précédente du même agent.
    """

    registry = AgentRegistry()

    registry.register(
        create_climate_agent(priority=5)
    )

    registry.register(
        create_climate_agent(priority=9)
    )

    result = registry.find_by_name(
        "adip.climate_agent"
    )

    assert result is not None
    assert result.priority == 9
    assert registry.count() == 1


def test_unregister_agent():
    """
    Vérifie la suppression d'un agent.
    """

    registry = AgentRegistry()
    registry.register(create_climate_agent())

    registry.unregister(
        "adip.climate_agent"
    )

    assert registry.count() == 0
    assert (
        registry.find_by_name(
            "adip.climate_agent"
        )
        is None
    )


def test_unregister_unknown_agent_raises_error():
    """
    Vérifie qu'une suppression invalide lève une erreur.
    """

    registry = AgentRegistry()

    with pytest.raises(KeyError):
        registry.unregister(
            "adip.unknown_agent"
        )


def test_find_available_agents():
    """
    Vérifie que seuls les agents disponibles sont retournés.
    """

    registry = AgentRegistry()

    registry.register(
        create_climate_agent(
            status=AgentStatus.AVAILABLE
        )
    )

    stopped_agent = AgentDescriptor(
        name="adip.stopped_agent",
        display_name="Stopped Agent",
        product="ADIP",
        queue_name="adip.stopped",
        status=AgentStatus.STOPPED,
    )

    registry.register(stopped_agent)

    available_agents = (
        registry.find_available_agents()
    )

    assert len(available_agents) == 1
    assert (
        available_agents[0].name
        == "adip.climate_agent"
    )


def test_find_agents_by_capability_sorted_by_priority():
    """
    Vérifie la recherche par capacité
    et le tri par priorité décroissante.
    """

    registry = AgentRegistry()

    registry.register(
        create_backup_climate_agent()
    )

    registry.register(
        create_climate_agent(priority=8)
    )

    results = registry.find_by_capability(
        "drought_analysis"
    )

    assert len(results) == 2
    assert (
        results[0].name
        == "adip.climate_agent"
    )
    assert (
        results[1].name
        == "adip.backup_climate_agent"
    )


def test_find_by_capability_excludes_stopped_agents():
    """
    Vérifie que les agents arrêtés sont exclus par défaut.
    """

    registry = AgentRegistry()

    registry.register(
        create_climate_agent(
            status=AgentStatus.STOPPED
        )
    )

    results = registry.find_by_capability(
        "drought_analysis"
    )

    assert results == []


def test_find_by_capability_can_include_unavailable_agents():
    """
    Vérifie qu'on peut demander tous les agents,
    même indisponibles.
    """

    registry = AgentRegistry()

    registry.register(
        create_climate_agent(
            status=AgentStatus.STOPPED
        )
    )

    results = registry.find_by_capability(
        "drought_analysis",
        only_available=False,
    )

    assert len(results) == 1


def test_update_agent_status():
    """
    Vérifie la mise à jour du statut.
    """

    registry = AgentRegistry()

    registry.register(
        create_climate_agent(
            status=AgentStatus.STOPPED
        )
    )

    updated_agent = registry.update_status(
        agent_name="adip.climate_agent",
        status=AgentStatus.AVAILABLE,
    )

    assert (
        updated_agent.status
        == AgentStatus.AVAILABLE
    )

    stored_agent = registry.find_by_name(
        "adip.climate_agent"
    )

    assert stored_agent is not None
    assert stored_agent.is_available() is True