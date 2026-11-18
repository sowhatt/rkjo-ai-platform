"""Concrete transport-backed MCP client for RKJO Tool Runtime."""

from __future__ import annotations

from typing import Any

from rkjo_kernel.tools.context import ToolExecutionContext
from rkjo_kernel.tools.mcp.client import MCPClient, MCPRemoteTool
from rkjo_kernel.tools.mcp.credentials import (
    EmptyMCPCredentialProvider,
    MCPCredentialProvider,
)
from rkjo_kernel.tools.mcp.transport import MCPTransport


class TransportMCPClient(MCPClient):
    """MCP client that delegates protocol I/O to an injected transport."""

    def __init__(
        self,
        *,
        transport: MCPTransport,
        server_name: str,
        credential_provider: MCPCredentialProvider | None = None,
        timeout_ms: int = 30_000,
    ) -> None:
        normalized_server_name = server_name.strip().lower()

        if not normalized_server_name:
            raise ValueError("MCP server name cannot be empty.")

        if timeout_ms <= 0:
            raise ValueError("MCP timeout_ms must be greater than zero.")

        self.transport = transport
        self.server_name = normalized_server_name
        self.credential_provider = (
            credential_provider or EmptyMCPCredentialProvider()
        )
        self.timeout_ms = timeout_ms

    def list_tools(self) -> list[MCPRemoteTool]:
        result = self.transport.request(
            method="tools/list",
            params={},
            headers={},
            timeout_ms=self.timeout_ms,
        )

        raw_tools = result.get("tools", []) if isinstance(result, dict) else []

        return [
            MCPRemoteTool(
                name=item["name"],
                description=item.get("description", ""),
                input_schema=dict(item.get("inputSchema", {})),
            )
            for item in raw_tools
        ]

    def call_tool(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        context: ToolExecutionContext | None = None,
    ) -> Any:
        if context is None:
            raise PermissionError(
                "MCP tool execution requires a ToolExecutionContext."
            )

        headers = self.credential_provider.get_headers(
            tenant_id=context.tenant_id,
            server_name=self.server_name,
        )

        return self.transport.request(
            method="tools/call",
            params={
                "name": tool_name,
                "arguments": arguments,
            },
            headers=headers,
            timeout_ms=self.timeout_ms,
        )
