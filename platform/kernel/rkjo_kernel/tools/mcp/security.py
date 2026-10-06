"""Inbound MCP authentication and authorization boundary for RKJO."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from rkjo_kernel.tools.context import ToolExecutionContext


@dataclass(frozen=True, slots=True)
class MCPPrincipal:
    principal_id: str
    tenant_id: str
    allowed_capabilities: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        principal = self.principal_id.strip()
        tenant = self.tenant_id.strip().lower()
        if not principal:
            raise ValueError("MCP principal_id cannot be empty.")
        if not tenant or " " in tenant:
            raise ValueError("MCP tenant_id must be a valid routing identifier.")
        object.__setattr__(self, "principal_id", principal)
        object.__setattr__(self, "tenant_id", tenant)
        object.__setattr__(
            self,
            "allowed_capabilities",
            frozenset(
                item.strip().lower()
                for item in self.allowed_capabilities
                if item.strip()
            ),
        )


class MCPAuthenticator(Protocol):
    def authenticate(self, credential: str) -> MCPPrincipal: ...


class MappingMCPAuthenticator:
    """Simple secret-to-principal mapping for tests/bootstrap.

    Production transports can replace this with OAuth/OIDC/API-key validation
    behind the same MCPAuthenticator contract.
    """

    def __init__(self, principals: dict[str, MCPPrincipal]) -> None:
        self._principals = dict(principals)

    def authenticate(self, credential: str) -> MCPPrincipal:
        if not isinstance(credential, str) or not credential.strip():
            raise PermissionError("MCP authentication credential is required.")
        principal = self._principals.get(credential)
        if principal is None:
            raise PermissionError("Invalid MCP authentication credential.")
        return principal


class MCPServerSecurity:
    def __init__(self, authenticator: MCPAuthenticator) -> None:
        self.authenticator = authenticator

    def authorize(
        self,
        *,
        credential: str,
        capability_name: str,
        agent_name: str,
        mission_id: str | None = None,
        trace_id: str | None = None,
        workflow_execution_id: str | None = None,
        workflow_step_id: str | None = None,
        correlation_id: str | None = None,
        metadata: dict | None = None,
    ) -> ToolExecutionContext:
        principal = self.authenticator.authenticate(credential)
        capability = capability_name.strip().lower()

        if capability not in principal.allowed_capabilities:
            raise PermissionError(
                f"MCP principal '{principal.principal_id}' is not authorized "
                f"for capability '{capability}'."
            )

        safe_metadata = dict(metadata or {})
        # Canonical authenticated identity always wins over caller metadata.
        safe_metadata["mcp_principal_id"] = principal.principal_id
        safe_metadata["mcp_authenticated_tenant_id"] = principal.tenant_id

        return ToolExecutionContext(
            tenant_id=principal.tenant_id,
            agent_name=agent_name,
            capability_name=capability,
            mission_id=mission_id,
            trace_id=trace_id,
            workflow_execution_id=workflow_execution_id,
            workflow_step_id=workflow_step_id,
            correlation_id=correlation_id,
            metadata=safe_metadata,
        )
