"""Tenant-aware credential providers for MCP calls."""

from __future__ import annotations

from abc import ABC, abstractmethod


class MCPCredentialProvider(ABC):
    """Resolve outbound MCP headers for one tenant and server."""

    @abstractmethod
    def get_headers(
        self,
        *,
        tenant_id: str,
        server_name: str,
    ) -> dict[str, str]:
        raise NotImplementedError


class EmptyMCPCredentialProvider(MCPCredentialProvider):
    """Credential provider for MCP servers that require no authentication."""

    def get_headers(
        self,
        *,
        tenant_id: str,
        server_name: str,
    ) -> dict[str, str]:
        return {}


class MappingMCPCredentialProvider(MCPCredentialProvider):
    """In-memory tenant/server credential mapping for tests and bootstrapping."""

    def __init__(
        self,
        credentials: dict[tuple[str, str], dict[str, str]],
    ) -> None:
        self._credentials = {
            (
                tenant_id.strip().lower(),
                server_name.strip().lower(),
            ): dict(headers)
            for (tenant_id, server_name), headers in credentials.items()
        }

    def get_headers(
        self,
        *,
        tenant_id: str,
        server_name: str,
    ) -> dict[str, str]:
        key = (
            tenant_id.strip().lower(),
            server_name.strip().lower(),
        )

        headers = self._credentials.get(key)

        if headers is None:
            raise PermissionError(
                f"No MCP credentials configured for tenant '{key[0]}' "
                f"and server '{key[1]}'."
            )

        return dict(headers)
