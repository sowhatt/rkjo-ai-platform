from abc import ABC, abstractmethod
from typing import Any

from rkjo_kernel.events.event_bus import EventBus
from rkjo_kernel.logging.logger import get_logger
from rkjo_kernel.messages.agent_message import AgentMessage


class BaseAgent(ABC):
    """
    Classe de base de tous les agents de RKJO AI Platform.

    Pourquoi cette classe ?

    Tous les agents auront des comportements communs :

    - une identité ;
    - une file RabbitMQ à écouter ;
    - un cycle de vie start / stop ;
    - un statut ;
    - des logs ;
    - une méthode health ;
    - un traitement standardisé des AgentMessage.

    Les agents spécialisés n'auront donc qu'à développer
    leur logique métier dans la méthode process().
    """

    def __init__(
        self,
        agent_name: str,
        queue_name: str,
        event_bus: EventBus,
    ) -> None:
        """
        Initialise l'agent sans démarrer immédiatement sa consommation.

        Paramètres :

        agent_name :
            Nom technique unique de l'agent.
            Exemple : adip.climate_agent

        queue_name :
            File RabbitMQ écoutée par l'agent.
            Exemple : adip.climate

        event_bus :
            Bus utilisé pour recevoir les missions.

        Pourquoi injecter EventBus ?

        L'agent ne dépend pas directement de RabbitMQ.
        Il dépend uniquement du contrat abstrait EventBus.

        Cela facilite :
        - les tests ;
        - le remplacement de RabbitMQ ;
        - l'utilisation future de Kafka ou Redis Streams.
        """

        self.agent_name = agent_name
        self.queue_name = queue_name
        self.event_bus = event_bus

        self.logger = get_logger(
            f"rkjo.agents.{self.agent_name}"
        )

        self.is_running = False
        self.processed_messages = 0
        self.failed_messages = 0

    def start(self) -> None:
        """
        Démarre l'agent et commence l'écoute de sa file.

        Cette méthode est bloquante avec notre implémentation RabbitMQ actuelle :
        le processus attend continuellement de nouveaux messages.
        """

        if self.is_running:
            self.logger.warning(
                "Agent '%s' is already running.",
                self.agent_name,
            )
            return

        self.logger.info(
            "Starting agent '%s' on queue '%s'...",
            self.agent_name,
            self.queue_name,
        )

        self.is_running = True

        try:
            self.event_bus.consume_agent_messages(
                queue_name=self.queue_name,
                callback=self._handle_message,
            )

        finally:
            # Si la consommation s'arrête, volontairement ou après erreur,
            # l'état de l'agent doit redevenir cohérent.
            self.is_running = False

    def stop(self) -> None:
        """
        Arrête proprement l'agent.

        Pour cette première version, l'arrêt ferme le bus d'événements.
        Nous améliorerons ensuite l'arrêt gracieux du consommateur RabbitMQ.
        """

        self.logger.info(
            "Stopping agent '%s'...",
            self.agent_name,
        )

        self.is_running = False
        self.event_bus.close()

        self.logger.info(
            "Agent '%s' stopped successfully.",
            self.agent_name,
        )

    def _handle_message(
        self,
        message: AgentMessage,
    ) -> Any:
        """
        Pipeline interne standard de traitement d'un message.

        Pourquoi ne pas appeler directement process() ?

        Cela permet d'encadrer tous les traitements avec les mêmes règles :

        1. validation de la cible ;
        2. hook avant traitement ;
        3. traitement métier ;
        4. hook après traitement ;
        5. statistiques ;
        6. gestion centralisée des erreurs.
        """

        self.logger.info(
            "Agent '%s' received message '%s'.",
            self.agent_name,
            message.message_id,
        )

        # Vérifie que le message est réellement destiné à cet agent.
        if message.target != self.agent_name:
            raise ValueError(
                f"Message target '{message.target}' does not match "
                f"agent '{self.agent_name}'."
            )

        try:
            self.before_process(message)

            result = self.process(message)

            self.after_process(
                message=message,
                result=result,
            )

            self.processed_messages += 1

            self.logger.info(
                "Agent '%s' processed message '%s' successfully.",
                self.agent_name,
                message.message_id,
            )

            return result

        except Exception:
            self.failed_messages += 1

            self.logger.exception(
                "Agent '%s' failed to process message '%s'.",
                self.agent_name,
                message.message_id,
            )

            # L'exception est remontée à EventBus.
            # RabbitMQ pourra alors effectuer un NACK.
            raise

    def before_process(
        self,
        message: AgentMessage,
    ) -> None:
        """
        Hook exécuté avant le traitement métier.

        Les futurs agents pourront le surcharger pour :
        - vérifier des autorisations ;
        - enrichir le contexte ;
        - démarrer une trace ;
        - charger une mémoire.
        """

    def after_process(
        self,
        message: AgentMessage,
        result: Any,
    ) -> None:
        """
        Hook exécuté après un traitement réussi.

        Les futurs agents pourront l'utiliser pour :
        - publier une réponse ;
        - enregistrer le résultat ;
        - produire une métrique ;
        - notifier l'orchestrateur.
        """

    @abstractmethod
    def process(
        self,
        message: AgentMessage,
    ) -> Any:
        """
        Méthode métier obligatoire.

        Chaque agent spécialisé devra l'implémenter.

        Exemple :

        ClimateAgent.process()
            analyse les données météorologiques.

        SoilAgent.process()
            analyse les données relatives aux sols.
        """

        raise NotImplementedError

    def health(self) -> dict[str, Any]:
        """
        Retourne l'état actuel de l'agent.

        Cette méthode alimentera plus tard :
        - les endpoints de santé ;
        - Grafana ;
        - Prometheus ;
        - l'orchestrateur ;
        - le tableau d'administration.
        """

        return {
            "agent_name": self.agent_name,
            "queue_name": self.queue_name,
            "status": (
                "running"
                if self.is_running
                else "stopped"
            ),
            "processed_messages": self.processed_messages,
            "failed_messages": self.failed_messages,
        }