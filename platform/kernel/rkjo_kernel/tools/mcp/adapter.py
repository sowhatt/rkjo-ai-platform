"""Adapter exposing MCP server tools through the RKJO Tool Runtime."""

from __future__ import annotations

from dataclasses import dataclass

from rkjo_kernel.tools.context import ToolExecutionContext
from rkjo_kernel.tools.descriptor import ToolDescriptor
from rkjo_kernel.tools.mcp.client import MCPClient, MCPRemoteTool
from rkjo_kernel.tools.registry import ToolRegistry


@dataclass(frozen=True)
class MCPToolRegistration:
    """Describe one MCP tool registered in RKJO."""

    remote_name: str
    rkjo_name: str


class MCPToolAdapter:
    """Register MCP tools as normal RKJO tools.

    MCP remains behind ToolRegistry/ToolInvoker so authorization and
    workflow behavior stay identical for local and remote tools.
    """

    def __init__(
        self,
        *,
        client: MCPClient,
        registry: ToolRegistry,
        server_name: str,
    ) -> None:
        normalized_server_name = server_name.strip().lower()

        if not normalized_server_name:
            raise ValueError("MCP server name cannot be empty.")

        if " " in normalized_server_name:
            raise ValueError("MCP server name must not contain spaces.")

        self.client = client
        self.registry = registry
        self.server_name = normalized_server_name

    def register_remote_tools(self) -> list[MCPToolRegistration]:
        registrations: list[MCPToolRegistration] = []

        for remote_tool in self.client.list_tools():
            rkjo_name = self._rkjo_tool_name(remote_tool)

            self.registry.register(
                self._to_descriptor(
                    remote_tool=remote_tool,
                    rkjo_name=rkjo_name,
                ),
                handler=self._build_handler(remote_tool.name),
            )

            registrations.append(
                MCPToolRegistration(
                    remote_name=remote_tool.name,
                    rkjo_name=rkjo_name,
                )
            )

        return registrations

    def _to_descriptor(
        self,
        *,
        remote_tool: MCPRemoteTool,
        rkjo_name: str,
    ) -> ToolDescriptor:
        return ToolDescriptor(
            name=rkjo_name,
            display_name=remote_tool.name,
            description=remote_tool.description or remote_tool.name,
            input_schema=dict(remote_tool.input_schema),
            tags=["mcp"],
            metadata={
                "transport": "mcp",
                "mcp_server": self.server_name,
                "mcp_tool_name": remote_tool.name,
            },
        )

    def _build_handler(self, remote_tool_name: str):
        def handler(
            payload: dict,
            context: ToolExecutionContext,
        ):
            result = self.client.call_tool(
                tool_name=remote_tool_name,
                arguments=payload,
                context=context,
            )

            return {
                "server": self.server_name,
                "remote_tool": remote_tool_name,
                "tenant_id": context.tenant_id,
                "result": result,
            }

        return handler

    def _rkjo_tool_name(self, remote_tool: MCPRemoteTool) -> str:
        normalized_remote_name = (
            remote_tool.name.strip().lower().replace(" ", "_")
        )
        return f"mcp.{self.server_name}.{normalized_remote_name}"
