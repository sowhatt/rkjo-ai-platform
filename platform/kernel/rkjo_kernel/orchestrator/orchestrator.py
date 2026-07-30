from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.logging.logger import get_logger
from rkjo_kernel.messages.agent_message import AgentMessage
from rkjo_kernel.registry.discovery import (
    AgentDiscovery,
    DiscoveryCriteria,
    DiscoveryResult,
)


@dataclass(frozen=True)
class MissionRequest:
    """
    Mission reçue par l'Orchestrator.

    Pourquoi une classe dédiée ?

    L'Orchestrator ne doit pas recevoir une multitude de paramètres isolés.
    MissionRequest regroupe le besoin fonctionnel et les contraintes
    utilisées pour découvrir le meilleur agent.
    """

    # Compétence nécessaire pour traiter la mission.
    capability_name: str

    # Données métier transmises à l'agent.
    payload: dict[str, Any]

    # Produit à l'origine de la mission.
    product: str = "RKJO"

    # Composant ou utilisateur qui envoie la mission.
    source: str = "rkjo.orchestrator"

    # Priorité RabbitMQ comprise entre 1 et 10.
    priority: int = 5

    # Critères facultatifs de découverte.
    region: str | None = None
    language: str | None = None
    max_cost: float | None = None
    max_duration_ms: int | None = None

    # Identifiant commun à toute une décision multi-agents.
    correlation_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    # Métadonnées de traçabilité.
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class DispatchPlan:
    """
    Plan de routage préparé sans publication.

    Il contient :
    - l'agent sélectionné ;
    - le message construit ;
    - la queue cible ;
    - les informations de découverte.
    """

    message: AgentMessage
    discovery: DiscoveryResult
    queue_name: str


@dataclass(frozen=True)
class DispatchResult:
    """
    Résultat d'un envoi de mission.

    Il permet de savoir :
    - quel agent a été choisi ;
    - quelle queue a été utilisée ;
    - quel message a été publié ;
    - quel score de découverte a été obtenu.
    """

    message: AgentMessage
    discovery: DiscoveryResult
    queue_name: str


class OrchestrationError(Exception):
    """
    Erreur de base liée à l'orchestration.
    """


class NoSuitableAgentError(OrchestrationError):
    """
    Erreur levée lorsqu'aucun agent compatible n'est disponible.
    """


class AgentOrchestrator:
    """
    Orchestrateur générique de RKJO AI Platform.

    Responsabilités :

    1. recevoir une MissionRequest ;
    2. rechercher le meilleur agent ;
    3. construire un AgentMessage ;
    4. envoyer la mission sur la queue de l'agent ;
    5. retourner les informations de traçabilité.

    Ce composant ne connaît pas RabbitMQ.
    Il dépend uniquement de l'interface EventBus.
    """

    def __init__(
        self,
        discovery: AgentDiscovery,
        event_bus: EventBus,
    ) -> None:
        """
        Les dépendances sont injectées pour préserver l'isolation.

        Cela permet notamment :
        - d'utiliser RabbitMQ en production ;
        - d'utiliser un faux bus pendant les tests ;
        - d'ajouter Kafka plus tard ;
        - de remplacer la stratégie de découverte.
        """

        self.discovery = discovery
        self.event_bus = event_bus
        self.logger = get_logger(
            "rkjo.orchestrator"
        )

    def plan(
        self,
        request: MissionRequest,
    ) -> DispatchPlan:
        """
        Discover the best agent and build a dispatch plan.

        This method does not publish the message.
        """

        self.logger.info(
            "Planning agent dispatch for capability '%s' "
            "with correlation_id '%s'.",
            request.capability_name,
            request.correlation_id,
        )

        discovery_result = self.discovery.discover(
            DiscoveryCriteria(
                capability_name=request.capability_name,
                region=request.region,
                language=request.language,
                max_cost=request.max_cost,
                max_duration_ms=request.max_duration_ms,
            )
        )

        if discovery_result is None:
            self.logger.warning(
                "No suitable agent found for capability '%s'.",
                request.capability_name,
            )

            raise NoSuitableAgentError(
                "No available agent matches capability "
                f"'{request.capability_name}'."
            )

        selected_agent = discovery_result.agent

        message = AgentMessage(
            correlation_id=request.correlation_id,
            source=request.source,
            target=selected_agent.name,
            message_type="mission",
            priority=request.priority,
            payload=request.payload,
            metadata={
                **request.metadata,
                "product": request.product,
                "requested_capability": (
                    request.capability_name
                ),
                "selected_agent_version": (
                    selected_agent.version
                ),
                "discovery_score": (
                    discovery_result.score
                ),
            },
        )

        return DispatchPlan(
            message=message,
            discovery=discovery_result,
            queue_name=selected_agent.queue_name,
        )

    def dispatch(
        self,
        request: MissionRequest,
    ) -> DispatchResult:
        """
        Plan and publish a mission to the selected agent.
        """

        plan = self.plan(request)

        self.event_bus.publish_agent_message(
            queue_name=plan.queue_name,
            message=plan.message,
        )

        self.logger.info(
            "Mission '%s' dispatched to agent '%s' "
            "through queue '%s'.",
            plan.message.message_id,
            plan.discovery.agent.name,
            plan.queue_name,
        )

        return DispatchResult(
            message=plan.message,
            discovery=plan.discovery,
            queue_name=plan.queue_name,
        )
