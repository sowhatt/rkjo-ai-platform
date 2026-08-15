"""Resolve workflow steps to registered agents and queues."""

from __future__ import annotations

from dataclasses import dataclass

from rkjo_kernel.registry.descriptor import AgentDescriptor
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.workflow.models.workflow_step import WorkflowStep


@dataclass(frozen=True, slots=True)
class AgentRoute:
    """Resolved execution route for one workflow step."""

    agent_name: str
    queue_name: str


class WorkflowAgentRouter:
    """Resolve workflow step routing through the Registry."""

    def __init__(
        self,
        *,
        registry_service: RegistryService,
    ) -> None:
        self.registry_service = registry_service

    def resolve(
        self,
        step: WorkflowStep,
    ) -> AgentRoute:
        """Resolve one step to a registered available agent."""

        if step.agent_name:
            descriptor = self.registry_service.get_agent(
                step.agent_name
            )

            if descriptor is None:
                raise LookupError(
                    f"Agent '{step.agent_name}' "
                    "is not registered."
                )

            if not descriptor.is_available():
                raise LookupError(
                    f"Agent '{descriptor.name}' "
                    "is not available."
                )

            return self._to_route(
                descriptor
            )

        if step.capability_name:
            agents = (
                self.registry_service
                .find_agents_by_capability(
                    step.capability_name,
                    only_available=True,
                )
            )

            if not agents:
                raise LookupError(
                    "No available agent found for "
                    f"capability "
                    f"'{step.capability_name}'."
                )

            return self._to_route(
                agents[0]
            )

        raise ValueError(
            "Workflow step must define either "
            "agent_name or capability_name."
        )

    @staticmethod
    def _to_route(
        descriptor: AgentDescriptor,
    ) -> AgentRoute:
        return AgentRoute(
            agent_name=descriptor.name,
            queue_name=descriptor.queue_name,
        )
