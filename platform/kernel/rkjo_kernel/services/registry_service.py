from rkjo_kernel.logging.logger import get_logger
from rkjo_kernel.registry.descriptor import (
    AgentDescriptor,
    AgentStatus,
)
from rkjo_kernel.registry.registry import AgentRegistry


class RegistryService:
    """
    Service applicatif chargé de gérer les agents enregistrés.

    Pourquoi cette classe ?

    AgentRegistry reste volontairement simple :
    il stocke et recherche des AgentDescriptor.

    RegistryService ajoute les responsabilités applicatives :

    - validation avant enregistrement ;
    - journalisation ;
    - gestion des statuts ;
    - préparation des futures notifications ;
    - préparation de l'audit ;
    - point d'entrée stable pour l'orchestrateur.

    Ainsi, l'orchestrateur ne manipule pas directement le stockage
    interne du registre.
    """

    def __init__(
        self,
        registry: AgentRegistry,
    ) -> None:
        """
        Initialise le service avec un registre injecté.

        Pourquoi injecter AgentRegistry ?

        Cela évite de créer le registre directement dans le service.

        Avantages :
        - tests plus simples ;
        - remplacement futur par un autre stockage ;
        - meilleure isolation ;
        - respect de l'inversion de dépendances.
        """

        self.registry = registry
        self.logger = get_logger(
            "rkjo.services.registry"
        )

    def register_agent(
        self,
        descriptor: AgentDescriptor,
    ) -> AgentDescriptor:
        """
        Enregistre ou met à jour un agent.

        Retourne le descripteur enregistré.
        """

        existing_agent = self.registry.find_by_name(
            descriptor.name
        )

        if existing_agent is None:
            self.logger.info(
                "Registering agent '%s'.",
                descriptor.name,
            )
        else:
            self.logger.info(
                "Updating registered agent '%s' "
                "from version '%s' to '%s'.",
                descriptor.name,
                existing_agent.version,
                descriptor.version,
            )

        self.registry.register(descriptor)

        self.logger.info(
            "Agent '%s' registered successfully.",
            descriptor.name,
        )

        return descriptor

    def unregister_agent(
        self,
        agent_name: str,
    ) -> None:
        """
        Supprime un agent du registre.

        La logique de stockage reste dans AgentRegistry.
        Le service ajoute les logs et servira plus tard
        de point d'audit.
        """

        self.logger.info(
            "Unregistering agent '%s'.",
            agent_name,
        )

        self.registry.unregister(agent_name)

        self.logger.info(
            "Agent '%s' unregistered successfully.",
            agent_name,
        )

    def get_agent(
        self,
        agent_name: str,
    ) -> AgentDescriptor | None:
        """
        Recherche un agent par son nom technique.
        """

        return self.registry.find_by_name(agent_name)

    def list_agents(
        self,
    ) -> list[AgentDescriptor]:
        """
        Retourne tous les agents enregistrés.
        """

        return self.registry.list_agents()

    def list_available_agents(
        self,
    ) -> list[AgentDescriptor]:
        """
        Retourne seulement les agents disponibles.
        """

        return self.registry.find_available_agents()

    def find_agents_by_capability(
        self,
        capability_name: str,
        only_available: bool = True,
    ) -> list[AgentDescriptor]:
        """
        Recherche les agents possédant une compétence donnée.

        Cette méthode sera utilisée prochainement
        par AgentDiscovery.
        """

        self.logger.debug(
            "Searching agents for capability '%s'.",
            capability_name,
        )

        return self.registry.find_by_capability(
            capability_name=capability_name,
            only_available=only_available,
        )

    def update_agent_status(
        self,
        agent_name: str,
        status: AgentStatus,
    ) -> AgentDescriptor:
        """
        Met à jour le statut d'un agent.

        Exemples :
        - stopped vers available ;
        - available vers busy ;
        - busy vers available ;
        - available vers error.
        """

        self.logger.info(
            "Updating agent '%s' status to '%s'.",
            agent_name,
            status.value,
        )

        updated_agent = self.registry.update_status(
            agent_name=agent_name,
            status=status,
        )

        self.logger.info(
            "Agent '%s' status updated successfully.",
            agent_name,
        )

        return updated_agent

    def count_agents(self) -> int:
        """
        Retourne le nombre total d'agents enregistrés.
        """

        return self.registry.count()