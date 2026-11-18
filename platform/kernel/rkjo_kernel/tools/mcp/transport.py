"""Transport contracts for MCP client implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MCPTransportError(RuntimeError):
    """Base error raised when an MCP transport cannot complete a request."""


class MCPTransportTimeoutError(MCPTransportError):
    """Raised when an MCP request exceeds its configured timeout."""


class MCPTransport(ABC):
    """Synchronous transport boundary used by the kernel MCP client."""

    @abstractmethod
    def request(
        self,
        *,
        method: str,
        params: dict[str, Any],
        headers: dict[str, str],
        timeout_ms: int,
    ) -> Any:
        """Execute one MCP request and return its decoded result."""
        raise NotImplementedError
