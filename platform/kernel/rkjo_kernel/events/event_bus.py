from abc import ABC, abstractmethod
from typing import Callable


class EventBus(ABC):
    """
    Interface abstraite du bus d'événements.

    Pourquoi ?
    Le Kernel ne doit pas dépendre directement de RabbitMQ.
    Il dépend d'un contrat générique : publier, consommer, fermer.

    Demain, on pourra remplacer RabbitMQ par Kafka, Redis Streams
    ou un bus mémoire sans changer le reste de la plateforme.
    """

    @abstractmethod
    def publish(self, queue_name: str, message: str) -> None:
        """
        Publie un message dans une file.

        Exemple :
        envoyer une tâche à l'Agent Climat.
        """
        pass

    @abstractmethod
    def consume(self, queue_name: str, callback: Callable[[str], None]) -> None:
        """
        Consomme les messages d'une file.

        Exemple :
        un Agent Climat écoute la file 'agent.climat'.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        Ferme proprement la connexion au bus.

        Pourquoi ?
        Pour éviter les connexions ouvertes inutilement.
        """
        pass