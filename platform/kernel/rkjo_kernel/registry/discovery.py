from dataclasses import dataclass

from rkjo_kernel.registry.capability import AgentCapability
from rkjo_kernel.registry.descriptor import AgentDescriptor
from rkjo_kernel.services.registry_service import RegistryService


@dataclass(frozen=True)
class DiscoveryCriteria:
    """
    Critères utilisés pour sélectionner un agent.

    Pourquoi une classe dédiée ?

    Cela évite de multiplier les paramètres dans les méthodes
    et permettra d'ajouter plus tard :
    - une région ;
    - une langue ;
    - une version minimale ;
    - un coût maximum ;
    - une durée maximale ;
    - un modèle IA particulier.
    """

    capability_name: str
    region: str | None = None
    language: str | None = None
    max_cost: float | None = None
    max_duration_ms: int | None = None


@dataclass(frozen=True)
class DiscoveryResult:
    """
    Résultat détaillé de la sélection d'un agent.

    Pourquoi retourner davantage que l'agent ?

    L'orchestrateur doit pouvoir expliquer :
    - quel agent a été choisi ;
    - pour quelle capacité ;
    - avec quel score ;
    - selon quels critères.
    """

    agent: AgentDescriptor
    capability: AgentCapability
    score: float


class AgentDiscovery:
    """
    Service de découverte et de sélection des agents.

    Cette classe ne stocke aucun agent.
    Elle interroge uniquement RegistryService.

    Elle est également indépendante de RabbitMQ.
    """

    def __init__(
        self,
        registry_service: RegistryService,
    ) -> None:
        self.registry_service = registry_service

    def discover(
        self,
        criteria: DiscoveryCriteria,
    ) -> DiscoveryResult | None:
        """
        Recherche le meilleur agent correspondant aux critères.

        Retourne None lorsqu'aucun agent compatible n'est disponible.
        """

        agents = self.registry_service.find_agents_by_capability(
            capability_name=criteria.capability_name,
            only_available=True,
        )

        candidates: list[DiscoveryResult] = []

        for agent in agents:
            capability = self._find_capability(
                agent=agent,
                capability_name=criteria.capability_name,
            )

            if capability is None:
                continue

            if not self._matches_filters(
                agent=agent,
                capability=capability,
                criteria=criteria,
            ):
                continue

            score = self._calculate_score(
                agent=agent,
                capability=capability,
            )

            candidates.append(
                DiscoveryResult(
                    agent=agent,
                    capability=capability,
                    score=score,
                )
            )

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda candidate: candidate.score,
        )

    @staticmethod
    def _find_capability(
        agent: AgentDescriptor,
        capability_name: str,
    ) -> AgentCapability | None:
        """
        Retrouve l'objet AgentCapability correspondant dans le descripteur.
        """

        normalized_name = capability_name.strip().lower()

        for capability in agent.capabilities:
            if capability.name == normalized_name:
                return capability

        return None

    @staticmethod
    def _matches_filters(
        agent: AgentDescriptor,
        capability: AgentCapability,
        criteria: DiscoveryCriteria,
    ) -> bool:
        """
        Vérifie les contraintes facultatives de la mission.
        """

        if (
            criteria.region is not None
            and criteria.region.lower()
            not in [
                region.lower()
                for region in agent.supported_regions
            ]
        ):
            return False

        if (
            criteria.language is not None
            and criteria.language.lower()
            not in [
                language.lower()
                for language in agent.supported_languages
            ]
        ):
            return False

        if (
            criteria.max_cost is not None
            and capability.estimated_cost
            > criteria.max_cost
        ):
            return False

        if (
            criteria.max_duration_ms is not None
            and capability.average_duration_ms
            > criteria.max_duration_ms
        ):
            return False

        return True

    @staticmethod
    def _calculate_score(
        agent: AgentDescriptor,
        capability: AgentCapability,
    ) -> float:
        """
        Calcule le score de sélection.

        Formule V1 :

        priorité de l'agent
        + confiance de la capacité
        - coût normalisé
        - durée normalisée

        Cette formule est volontairement simple et explicable.
        Elle pourra évoluer plus tard vers une politique configurable.
        """

        priority_score = agent.priority / 10
        confidence_score = capability.confidence_score

        cost_penalty = min(
            capability.estimated_cost / 100,
            1.0,
        )

        duration_penalty = min(
            capability.average_duration_ms / 60_000,
            1.0,
        )

        return (
            priority_score
            + confidence_score
            - cost_penalty
            - duration_penalty
        )