from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from rkjo_kernel.registry.capability import AgentCapability


class AgentStatus(StrEnum):
    """
    Statuts possibles d'un agent.

    Pourquoi ?

    Le Registry doit savoir si un agent est :
    - disponible ;
    - occupé ;
    - arrêté ;
    - en erreur ;
    - en maintenance.
    """

    AVAILABLE = "available"
    BUSY = "busy"
    STOPPED = "stopped"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class AgentDescriptor(BaseModel):
    """
    Description complète d'un agent enregistré dans RKJO AI Platform.

    Ce modèle ne contient pas le code de l'agent.
    Il décrit son identité, ses capacités et son état.

    Pourquoi séparer le descripteur de BaseAgent ?

    Cela permet au Registry de travailler uniquement avec des métadonnées,
    sans dépendre de RabbitMQ, du code métier ou du processus d'exécution.
    """

    # Nom technique unique.
    # Exemple : adip.climate_agent
    name: str

    # Nom lisible destiné aux utilisateurs et administrateurs.
    display_name: str

    # Version de l'agent.
    version: str = "1.0.0"

    # Description fonctionnelle.
    description: str = ""

    # Produit auquel appartient l'agent.
    # Exemple : ADIP, AssurGov, SecureVision.
    product: str

    # File logique associée à l'agent.
    #
    # Le Registry stocke cette information,
    # mais ne connaît pas RabbitMQ directement.
    queue_name: str

    # État courant.
    status: AgentStatus = AgentStatus.STOPPED

    # Liste des compétences déclarées.
    capabilities: list[AgentCapability] = Field(
        default_factory=list
    )

    # Priorité globale de sélection.
    #
    # Plus la valeur est élevée, plus l'agent peut être privilégié
    # lorsque plusieurs agents proposent la même capacité.
    priority: int = 5

    # Propriétaire fonctionnel ou technique.
    owner: str = "RKJO"

    # Zone géographique couverte.
    #
    # Exemple :
    # ["france", "europe"]
    supported_regions: list[str] = Field(
        default_factory=list
    )

    # Langues supportées.
    supported_languages: list[str] = Field(
        default_factory=lambda: ["fr"]
    )

    # Informations libres.
    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """
        Normalise le nom technique de l'agent.
        """

        normalized_value = value.strip().lower()

        if not normalized_value:
            raise ValueError(
                "Agent name cannot be empty."
            )

        if " " in normalized_value:
            raise ValueError(
                "Agent name must not contain spaces."
            )

        return normalized_value

    @field_validator("queue_name")
    @classmethod
    def validate_queue_name(cls, value: str) -> str:
        """
        Vérifie que le nom de file est exploitable.
        """

        normalized_value = value.strip().lower()

        if not normalized_value:
            raise ValueError(
                "Queue name cannot be empty."
            )

        if " " in normalized_value:
            raise ValueError(
                "Queue name must not contain spaces."
            )

        return normalized_value

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: int) -> int:
        """
        Limite la priorité à une valeur comprise entre 1 et 10.
        """

        if not 1 <= value <= 10:
            raise ValueError(
                "priority must be between 1 and 10."
            )

        return value

    def has_capability(
        self,
        capability_name: str,
    ) -> bool:
        """
        Indique si l'agent possède une capacité donnée.

        Pourquoi cette méthode ?

        Elle simplifie la recherche dans le futur AgentRegistry.
        """

        normalized_name = capability_name.strip().lower()

        return any(
            capability.name == normalized_name
            for capability in self.capabilities
        )

    def is_available(self) -> bool:
        """
        Indique si l'agent peut recevoir une mission.
        """

        return self.status == AgentStatus.AVAILABLE