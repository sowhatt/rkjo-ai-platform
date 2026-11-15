"""RKJO AI Platform composition root."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rkjo_kernel.config.settings import settings
from rkjo_kernel.exceptions.base import (
    KernelShutdownError,
    KernelStartupError,
)
from rkjo_kernel.logging.logger import get_logger
from rkjo_kernel.memory.context_engine import ContextEngine
from rkjo_kernel.memory.in_memory import InMemoryMemoryStore
from rkjo_kernel.registry.registry import AgentRegistry
from rkjo_kernel.runtime.context_runtime import AgentContextRuntime
from rkjo_kernel.services.registry_service import RegistryService
from rkjo_kernel.tools.invoker import ToolInvoker
from rkjo_kernel.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from rkjo_kernel.llm.gateway import LLMGateway


class RKJOKernel:
    """Composition root and lifecycle boundary of the RKJO AI Platform.

    The kernel assembles infrastructure-neutral core services.

    Production adapters such as PostgreSQL memory, RAG, MCP transports,
    LLM providers, RabbitMQ or Redis remain injectable and are not required
    to boot the local/test kernel.
    """

    def __init__(
        self,
        *,
        agent_registry: AgentRegistry | None = None,
        tool_registry: ToolRegistry | None = None,
        memory_store=None,
        context_engine: ContextEngine | None = None,
        llm_gateway: "LLMGateway | None" = None,
        owned_resources: tuple = (),
    ) -> None:
        self.settings = settings
        self.logger = get_logger("rkjo.kernel")

        # Agent/capability composition.
        self.agent_registry = agent_registry or AgentRegistry()
        self.registry_service = RegistryService(self.agent_registry)

        # Tool runtime composition.
        self.tool_registry = tool_registry or ToolRegistry()
        self.tool_invoker = ToolInvoker(self.tool_registry)

        # Memory/context composition.
        self.memory_store = memory_store or InMemoryMemoryStore()
        self.context_engine = context_engine or ContextEngine(
            store=self.memory_store
        )
        self.context_runtime = AgentContextRuntime(self.context_engine)

        # LLM infrastructure is optional until providers/router are configured.
        self.llm_gateway = llm_gateway

        self.is_started = False
        self._owned_resources = owned_resources
        self._closed = False

    def start(self) -> None:
        """Start the RKJO kernel lifecycle."""

        if self._closed:
            raise KernelStartupError("Closed kernel requires a new factory instance.")
        if self.is_started:
            return

        try:
            self.logger.info("Starting RKJO AI Kernel...")
            self.logger.info(
                "Application: %s",
                self.settings.app_name,
            )
            self.logger.info(
                "Environment: %s",
                self.settings.app_env,
            )

            self.is_started = True

            self.logger.info(
                "RKJO AI Kernel started successfully."
            )

        except Exception as exc:
            self.is_started = False
            raise KernelStartupError(
                "Failed to start RKJO AI Kernel"
            ) from exc

    def stop(self) -> None:
        """Stop the RKJO kernel lifecycle."""

        if self._closed:
            return

        try:
            self._closed = True
            self.is_started = False
            errors = []
            for resource in reversed(self._owned_resources):
                try:
                    resource.close()
                except Exception as exc:
                    errors.append(exc)
            if errors:
                raise ExceptionGroup("Kernel resource shutdown failed", errors)
            self.logger.info("Stopping RKJO AI Kernel...")

            self.is_started = False

            self.logger.info(
                "RKJO AI Kernel stopped successfully."
            )

        except Exception as exc:
            raise KernelShutdownError(
                "Failed to stop RKJO AI Kernel"
            ) from exc

    def health(self) -> dict:
        """Return platform and composed-component health information."""

        return {
            "app_name": self.settings.app_name,
            "environment": self.settings.app_env,
            "status": (
                "started"
                if self.is_started
                else "stopped"
            ),
            "components": {
                "agent_registry": {
                    "status": "ready",
                    "agents": self.agent_registry.count(),
                },
                "tool_registry": {
                    "status": "ready",
                    "tools": self.tool_registry.count(),
                    "bindings": self.tool_registry.count_bindings(),
                },
                "memory": {
                    "status": "ready",
                    "backend": self.memory_store.__class__.__name__,
                },
                "context_engine": {
                    "status": "ready",
                },
                "llm_gateway": {
                    "status": (
                        "ready"
                        if self.llm_gateway is not None
                        else "not_configured"
                    ),
                },
            },
        }
