import pytest
from pydantic import ValidationError

from rkjo_kernel.registry.capability import AgentCapability


def test_agent_capability_creation():
    """
    Vérifie qu'une capacité valide peut être créée.
    """

    capability = AgentCapability(
        name="drought_analysis",
        description=(
            "Analyse le risque de sécheresse "
            "pour une culture et un territoire."
        ),
        version="1.0.0",
        input_schema={
            "department_code": "str",
            "crop": "str",
        },
        output_schema={
            "risk_score": "float",
            "recommendations": "list[str]",
        },
        tags=[
            "climate",
            "agriculture",
            "france",
        ],
        confidence_score=0.85,
        estimated_cost=2.5,
        average_duration_ms=1200,
        supports_streaming=False,
        supports_local_model=True,
    )

    assert capability.name == "drought_analysis"
    assert capability.version == "1.0.0"
    assert capability.confidence_score == 0.85
    assert capability.supports_local_model is True
    assert "climate" in capability.tags


def test_capability_name_is_normalized():
    """
    Vérifie que le nom est automatiquement normalisé
    en minuscules et sans espaces aux extrémités.
    """

    capability = AgentCapability(
        name="  WEATHER_ANALYSIS  ",
        description="Analyse météorologique.",
    )

    assert capability.name == "weather_analysis"


def test_capability_rejects_name_with_spaces():
    """
    Vérifie qu'un nom technique avec des espaces est refusé.
    """

    with pytest.raises(ValidationError):
        AgentCapability(
            name="weather analysis",
            description="Nom invalide.",
        )


def test_capability_rejects_invalid_confidence_score():
    """
    Vérifie que le niveau de confiance reste compris entre 0 et 1.
    """

    with pytest.raises(ValidationError):
        AgentCapability(
            name="soil_analysis",
            description="Analyse de sol.",
            confidence_score=1.5,
        )


def test_capability_rejects_negative_cost():
    """
    Vérifie qu'un coût négatif est refusé.
    """

    with pytest.raises(ValidationError):
        AgentCapability(
            name="scientific_search",
            description="Recherche scientifique.",
            estimated_cost=-1,
        )