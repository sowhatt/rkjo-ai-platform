import pytest

from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.services.registry_service import (
    RegistryService,
)


def create_climate_agent(
    status: AgentStatus = AgentStatus.AVAILABLE,
    version: str = "1.0.0",
) -> AgentDescriptor:
    """
    Fabrique un descripteur d'Agent Climat
    réutilisable dans les tests.
    """

    return AgentDescriptor(
        name="adip.climate_agent",
        display_name="ADIP Climate Agent",
        version=version,
        description=(
            "Analyse les risques climatiques agricoles."
        ),
        product="ADIP",
        queue_name="adip.climate",
        status=status,
        priority=8,
        capabilities=[
            AgentCapability(
                name="drought_analysis",
                description=(
                    "Analyse du risque de sécheresse."
                ),
                confidence_score=0.9,
            )
        ],
    )


def test_registry_service_registers_agent():
    """
    Vérifie que le service enregistre correctement un agent.
    """

    registry = AgentRegistry()
    service = RegistryService(registry)

    descriptor = create_climate_agent()

    result = service.register_agent(descriptor)

    assert result.name == "adip.climate_agent"
    assert service.count_agents() == 1
    assert (
        service.get_agent(
            "adip.climate_agent"
        )
        is not None
    )


def test_registry_service_updates_existing_agent():
    """
    Vérifie qu'un agent existant peut être mis à jour.
    """

    registry = AgentRegistry()
    service = RegistryService(registry)

    service.register_agent(
        create_climate_agent(
            version="1.0.0"
        )
    )

    service.register_agent(
        create_climate_agent(
            version="2.0.0"
        )
    )

    stored_agent = service.get_agent(
        "adip.climate_agent"
    )

    assert stored_agent is not None
    assert stored_agent.version == "2.0.0"
    assert service.count_agents() == 1


def test_registry_service_unregisters_agent():
    """
    Vérifie qu'un agent peut être supprimé.
    """

    registry = AgentRegistry()
    service = RegistryService(registry)

    service.register_agent(
        create_climate_agent()
    )

    service.unregister_agent(
        "adip.climate_agent"
    )

    assert service.count_agents() == 0


def test_registry_service_raises_for_unknown_agent():
    """
    Vérifie qu'une suppression invalide lève une erreur.
    """

    registry = AgentRegistry()
    service = RegistryService(registry)

    with pytest.raises(KeyError):
        service.unregister_agent(
            "adip.unknown_agent"
        )


def test_registry_service_finds_by_capability():
    """
    Vérifie la recherche d'agents par compétence.
    """

    registry = AgentRegistry()
    service = RegistryService(registry)

    service.register_agent(
        create_climate_agent()
    )

    results = service.find_agents_by_capability(
        "drought_analysis"
    )

    assert len(results) == 1
    assert (
        results[0].name
        == "adip.climate_agent"
    )


def test_registry_service_updates_status():
    """
    Vérifie la mise à jour du statut via le service.
    """

    registry = AgentRegistry()
    service = RegistryService(registry)

    service.register_agent(
        create_climate_agent(
            status=AgentStatus.STOPPED
        )
    )

    updated_agent = service.update_agent_status(
        agent_name="adip.climate_agent",
        status=AgentStatus.AVAILABLE,
    )

    assert (
        updated_agent.status
        == AgentStatus.AVAILABLE
    )

    assert (
        len(service.list_available_agents())
        == 1
    )