"""Minimal MCP client contracts used by the RKJO Tool Runtime."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from rkjo_kernel.tools.context import ToolExecutionContext


@dataclass(frozen=True)
class MCPRemoteTool:
    """Metadata returned by an MCP server for one remote tool."""

    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized_name = self.name.strip()

        if not normalized_name:
            raise ValueError("MCP tool name cannot be empty.")

        object.__setattr__(self, "name", normalized_name)


class MCPClient(ABC):
    """Protocol boundary between RKJO and an MCP implementation."""

    @abstractmethod
    def list_tools(self) -> list[MCPRemoteTool]:
        """Return the tools currently exposed by the MCP server."""
        raise NotImplementedError

    @abstractmethod
    def call_tool(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        context: ToolExecutionContext | None = None,
    ) -> Any:
        """Execute one remote MCP tool."""
        raise NotImplementedError
