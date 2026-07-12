from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)


class AgentRegistry:
    """
    Registre central des agents de RKJO AI Platform.

    Pourquoi cette classe ?

    L'orchestrateur ne doit pas connaître les agents en dur.
    Il interroge le registre pour savoir :

    - quels agents existent ;
    - quelles capacités ils proposent ;
    - lesquels sont disponibles ;
    - quelle queue utiliser ;
    - quel agent choisir pour une mission.

    Le registre reste volontairement indépendant de RabbitMQ.
    Il ne gère que des métadonnées d'agents.
    """

    def __init__(self) -> None:
        """
        Initialise un registre vide.

        Pour cette première version, le stockage est en mémoire.

        Plus tard, nous pourrons ajouter un adaptateur PostgreSQL
        ou Redis sans modifier l'interface métier du registre.
        """

        self._agents: dict[str, AgentDescriptor] = {}

    def register(
        self,
        descriptor: AgentDescriptor,
    ) -> None:
        """
        Enregistre un agent.

        Si un agent portant déjà le même nom existe,
        il est remplacé par la nouvelle version du descripteur.

        Pourquoi ce comportement ?

        Cela facilite :
        - la mise à jour d'une version ;
        - le redémarrage d'un agent ;
        - le rafraîchissement de son état.
        """

        self._agents[descriptor.name] = descriptor

    def unregister(
        self,
        agent_name: str,
    ) -> None:
        """
        Supprime un agent du registre.

        Une erreur est levée si l'agent n'existe pas,
        afin d'éviter les suppressions silencieuses.
        """

        normalized_name = agent_name.strip().lower()

        if normalized_name not in self._agents:
            raise KeyError(
                f"Agent '{normalized_name}' is not registered."
            )

        del self._agents[normalized_name]

    def find_by_name(
        self,
        agent_name: str,
    ) -> AgentDescriptor | None:
        """
        Recherche un agent par son nom technique.

        Retourne None si l'agent n'existe pas.
        """

        normalized_name = agent_name.strip().lower()

        return self._agents.get(normalized_name)

    def list_agents(self) -> list[AgentDescriptor]:
        """
        Retourne tous les agents enregistrés.
        """

        return list(self._agents.values())

    def find_available_agents(
        self,
    ) -> list[AgentDescriptor]:
        """
        Retourne uniquement les agents disponibles.
        """

        return [
            descriptor
            for descriptor in self._agents.values()
            if descriptor.is_available()
        ]

    def find_by_capability(
        self,
        capability_name: str,
        only_available: bool = True,
    ) -> list[AgentDescriptor]:
        """
        Recherche les agents proposant une capacité donnée.

        Par défaut, seuls les agents disponibles sont retournés.

        Exemple :

        registry.find_by_capability(
            "drought_analysis"
        )
        """

        normalized_capability = (
            capability_name.strip().lower()
        )

        matching_agents = [
            descriptor
            for descriptor in self._agents.values()
            if descriptor.has_capability(
                normalized_capability
            )
        ]

        if only_available:
            matching_agents = [
                descriptor
                for descriptor in matching_agents
                if descriptor.is_available()
            ]

        # Tri par priorité décroissante.
        #
        # Pourquoi ?
        # Si plusieurs agents ont la même capacité,
        # le plus prioritaire apparaît en premier.
        return sorted(
            matching_agents,
            key=lambda descriptor: descriptor.priority,
            reverse=True,
        )

    def update_status(
        self,
        agent_name: str,
        status: AgentStatus,
    ) -> AgentDescriptor:
        """
        Met à jour le statut d'un agent.

        Retourne le descripteur mis à jour.
        """

        descriptor = self.find_by_name(agent_name)

        if descriptor is None:
            raise KeyError(
                f"Agent '{agent_name}' is not registered."
            )

        updated_descriptor = descriptor.model_copy(
            update={
                "status": status,
            }
        )

        self._agents[
            updated_descriptor.name
        ] = updated_descriptor

        return updated_descriptor

    def count(self) -> int:
        """
        Retourne le nombre d'agents enregistrés.
        """

        return len(self._agents)