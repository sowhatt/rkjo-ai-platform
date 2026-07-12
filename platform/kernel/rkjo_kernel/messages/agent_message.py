from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentMessage(BaseModel):
    """
    Message standard échangé entre l'orchestrateur et les agents.

    Pourquoi ?
    Dans une architecture multi-agents, il ne faut pas envoyer de simples textes.
    Chaque mission doit être traçable, routable et vérifiable.
    """

    # Identifiant unique du message
    message_id: str = Field(default_factory=lambda: str(uuid4()))

    # Identifiant commun à toute une décision / conversation
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))

    # Qui envoie le message
    source: str

    # Qui doit recevoir le message
    target: str

    # Type de message : mission, response, error, event...
    message_type: str = "mission"

    # Priorité de traitement : 1 faible, 10 très urgent
    priority: int = 5

    # Contenu métier de la mission
    payload: dict[str, Any]

    # Métadonnées techniques ou métier
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Date de création UTC
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))