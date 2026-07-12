import pytest
from pydantic import ValidationError

from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)


def create_drought_capability() -> AgentCapability:
    """
    Fabrique une capacité réutilisable dans les tests.
    """

    return AgentCapability(
        name="drought_analysis",
        description="Analyse du risque de sécheresse.",
        confidence_score=0.9,
        tags=[
            "climate",
            "agriculture",
        ],
    )


def test_agent_descriptor_creation():
    """
    Vérifie qu'un descripteur complet peut être créé.
    """

    descriptor = AgentDescriptor(
        name="adip.climate_agent",
        display_name="ADIP Climate Agent",
        version="1.0.0",
        description=(
            "Analyse les risques climatiques agricoles."
        ),
        product="ADIP",
        queue_name="adip.climate",
        status=AgentStatus.AVAILABLE,
        capabilities=[
            create_drought_capability()
        ],
        priority=8,
        supported_regions=[
            "france",
        ],
        supported_languages=[
            "fr",
            "en",
        ],
    )

    assert descriptor.name == "adip.climate_agent"
    assert descriptor.product == "ADIP"
    assert descriptor.status == AgentStatus.AVAILABLE
    assert descriptor.priority == 8
    assert descriptor.is_available() is True


def test_agent_descriptor_has_capability():
    """
    Vérifie la recherche d'une capacité.
    """

    descriptor = AgentDescriptor(
        name="adip.climate_agent",
        display_name="ADIP Climate Agent",
        product="ADIP",
        queue_name="adip.climate",
        capabilities=[
            create_drought_capability()
        ],
    )

    assert (
        descriptor.has_capability(
            "drought_analysis"
        )
        is True
    )

    assert (
        descriptor.has_capability(
            "soil_analysis"
        )
        is False
    )


def test_agent_descriptor_name_is_normalized():
    """
    Vérifie la normalisation automatique du nom.
    """

    descriptor = AgentDescriptor(
        name="  ADIP.CLIMATE_AGENT  ",
        display_name="Climate Agent",
        product="ADIP",
        queue_name="ADIP.CLIMATE",
    )

    assert descriptor.name == "adip.climate_agent"
    assert descriptor.queue_name == "adip.climate"


def test_agent_descriptor_rejects_invalid_priority():
    """
    Vérifie qu'une priorité invalide est refusée.
    """

    with pytest.raises(ValidationError):
        AgentDescriptor(
            name="adip.climate_agent",
            display_name="Climate Agent",
            product="ADIP",
            queue_name="adip.climate",
            priority=15,
        )


def test_stopped_agent_is_not_available():
    """
    Vérifie qu'un agent arrêté n'est pas sélectionnable.
    """

    descriptor = AgentDescriptor(
        name="adip.climate_agent",
        display_name="Climate Agent",
        product="ADIP",
        queue_name="adip.climate",
        status=AgentStatus.STOPPED,
    )

    assert descriptor.is_available() is False