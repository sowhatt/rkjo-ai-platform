from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.registry.discovery import (
    AgentDiscovery,
    DiscoveryCriteria,
)
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.services.registry_service import RegistryService


def create_agent(
    name: str,
    priority: int,
    confidence: float,
    cost: float,
    duration_ms: int,
    regions: list[str] | None = None,
    languages: list[str] | None = None,
    status: AgentStatus = AgentStatus.AVAILABLE,
) -> AgentDescriptor:
    """
    Fabrique un agent configurable pour les tests de sélection.
    """

    return AgentDescriptor(
        name=name,
        display_name=name,
        product="ADIP",
        queue_name=name.replace("_agent", ""),
        status=status,
        priority=priority,
        supported_regions=regions or ["france"],
        supported_languages=languages or ["fr"],
        capabilities=[
            AgentCapability(
                name="drought_analysis",
                description="Analyse du risque de sécheresse.",
                confidence_score=confidence,
                estimated_cost=cost,
                average_duration_ms=duration_ms,
            )
        ],
    )


def create_discovery() -> tuple[
    RegistryService,
    AgentDiscovery,
]:
    registry = AgentRegistry()
    service = RegistryService(registry)
    discovery = AgentDiscovery(service)

    return service, discovery


def test_discovery_selects_best_agent():
    """
    Vérifie que le meilleur score est sélectionné.
    """

    service, discovery = create_discovery()

    service.register_agent(
        create_agent(
            name="adip.fast_climate_agent",
            priority=8,
            confidence=0.9,
            cost=2,
            duration_ms=500,
        )
    )

    service.register_agent(
        create_agent(
            name="adip.expensive_climate_agent",
            priority=6,
            confidence=0.8,
            cost=50,
            duration_ms=10_000,
        )
    )

    result = discovery.discover(
        DiscoveryCriteria(
            capability_name="drought_analysis"
        )
    )

    assert result is not None
    assert (
        result.agent.name
        == "adip.fast_climate_agent"
    )
    assert result.score > 0


def test_discovery_filters_by_region():
    """
    Vérifie le filtrage géographique.
    """

    service, discovery = create_discovery()

    service.register_agent(
        create_agent(
            name="adip.france_agent",
            priority=5,
            confidence=0.8,
            cost=1,
            duration_ms=500,
            regions=["france"],
        )
    )

    result = discovery.discover(
        DiscoveryCriteria(
            capability_name="drought_analysis",
            region="france",
        )
    )

    assert result is not None
    assert result.agent.name == "adip.france_agent"


def test_discovery_rejects_wrong_region():
    """
    Vérifie qu'un agent incompatible avec la région est exclu.
    """

    service, discovery = create_discovery()

    service.register_agent(
        create_agent(
            name="adip.europe_agent",
            priority=8,
            confidence=0.9,
            cost=1,
            duration_ms=500,
            regions=["europe"],
        )
    )

    result = discovery.discover(
        DiscoveryCriteria(
            capability_name="drought_analysis",
            region="france",
        )
    )

    assert result is None


def test_discovery_filters_by_language():
    """
    Vérifie le filtrage linguistique.
    """

    service, discovery = create_discovery()

    service.register_agent(
        create_agent(
            name="adip.french_agent",
            priority=8,
            confidence=0.9,
            cost=1,
            duration_ms=500,
            languages=["fr"],
        )
    )

    result = discovery.discover(
        DiscoveryCriteria(
            capability_name="drought_analysis",
            language="fr",
        )
    )

    assert result is not None
    assert result.agent.name == "adip.french_agent"


def test_discovery_respects_maximum_cost():
    """
    Vérifie le filtre de coût maximum.
    """

    service, discovery = create_discovery()

    service.register_agent(
        create_agent(
            name="adip.expensive_agent",
            priority=10,
            confidence=1.0,
            cost=20,
            duration_ms=500,
        )
    )

    result = discovery.discover(
        DiscoveryCriteria(
            capability_name="drought_analysis",
            max_cost=5,
        )
    )

    assert result is None


def test_discovery_respects_maximum_duration():
    """
    Vérifie le filtre de durée maximale.
    """

    service, discovery = create_discovery()

    service.register_agent(
        create_agent(
            name="adip.slow_agent",
            priority=10,
            confidence=1.0,
            cost=1,
            duration_ms=20_000,
        )
    )

    result = discovery.discover(
        DiscoveryCriteria(
            capability_name="drought_analysis",
            max_duration_ms=2_000,
        )
    )

    assert result is None


def test_discovery_excludes_unavailable_agent():
    """
    Vérifie qu'un agent arrêté n'est jamais sélectionné.
    """

    service, discovery = create_discovery()

    service.register_agent(
        create_agent(
            name="adip.stopped_agent",
            priority=10,
            confidence=1.0,
            cost=0,
            duration_ms=1,
            status=AgentStatus.STOPPED,
        )
    )

    result = discovery.discover(
        DiscoveryCriteria(
            capability_name="drought_analysis"
        )
    )

    assert result is None


def test_discovery_returns_none_for_unknown_capability():
    """
    Vérifie le comportement lorsqu'aucun agent ne possède la capacité.
    """

    service, discovery = create_discovery()

    service.register_agent(
        create_agent(
            name="adip.climate_agent",
            priority=8,
            confidence=0.9,
            cost=1,
            duration_ms=500,
        )
    )

    result = discovery.discover(
        DiscoveryCriteria(
            capability_name="soil_analysis"
        )
    )

    assert result is None