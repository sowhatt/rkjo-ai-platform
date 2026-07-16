from abc import ABC, abstractmethod
from collections.abc import Callable

from rkjo_kernel.messages.agent_message import AgentMessage


class EventBus(ABC):
    """
    Interface abstraite du bus d'événements.

    Pourquoi ?

    Le Kernel ne doit pas dépendre directement de RabbitMQ.
    Il dépend d'un contrat générique permettant de :

    - publier un message texte ;
    - consommer un message texte ;
    - publier un AgentMessage structuré ;
    - consommer un AgentMessage structuré ;
    - fermer proprement la connexion.

    Cela permettra plus tard d'ajouter Kafka, Redis Streams
    ou un bus en mémoire sans modifier les agents ni l'Orchestrator.
    """

    @abstractmethod
    def publish(
        self,
        queue_name: str,
        message: str,
    ) -> None:
        """
        Publie un message texte dans une file.
        """

        pass

    @abstractmethod
    def consume(
        self,
        queue_name: str,
        callback: Callable[[str], None],
    ) -> None:
        """
        Consomme les messages texte d'une file.
        """

        pass

    @abstractmethod
    def publish_agent_message(
        self,
        queue_name: str,
        message: AgentMessage,
    ) -> None:
        """
        Publie un AgentMessage structuré.

        L'Orchestrator peut ainsi envoyer une mission sans connaître
        RabbitMQ, Kafka ou une autre technologie de transport.
        """

        pass

    @abstractmethod
    def consume_agent_messages(
        self,
        queue_name: str,
        callback: Callable[[AgentMessage], None],
    ) -> None:
        """
        Consomme des AgentMessage validés.

        Les agents dépendent du contrat EventBus,
        et non d'une technologie de messagerie particulière.
        """

        pass

    @abstractmethod
    def close(self) -> None:
        """
        Ferme proprement la connexion au bus.
        """

        pass