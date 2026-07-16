from enum import StrEnum


class RuntimeStatus(StrEnum):
    """
    États possibles d'un AgentRuntime.

    Pourquoi les distinguer du statut d'un AgentDescriptor ?

    AgentDescriptor représente l'état public connu du Registry.

    RuntimeStatus représente l'état technique réel du processus
    qui exécute l'agent.
    """

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"