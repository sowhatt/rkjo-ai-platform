"""Synchronous facade over the MCP SDK's initialized stdio session."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
from typing import Any, Mapping

from rkjo_kernel.tools.mcp.transport import MCPTransport, MCPTransportError, MCPTransportTimeoutError


class StdioMCPTransport(MCPTransport):
    """One initialized, closed session per request; no credentials in logs.

    The SDK owns framing, protocol negotiation and response-ID matching.
    HTTP authorization headers have no meaning on this local transport.
    Explicit subprocess environment overrides are operator configuration.
    """

    def __init__(self, *, command: str, args: list[str] | None = None,
                 env: Mapping[str, str] | None = None, cwd: str | None = None,
                 client_name: str = "rkjo-ai-platform", client_version: str = "1.0.0") -> None:
        if not command.strip():
            raise ValueError("MCP stdio command cannot be empty.")
        self.command = command.strip()
        self.args = list(args or [])
        self.env = dict(env or {})
        self.cwd = cwd
        self.client_name = client_name.strip() or "rkjo-ai-platform"
        self.client_version = client_version.strip() or "1.0.0"

    def request(self, *, method: str, params: dict[str, Any],
                headers: dict[str, str], timeout_ms: int) -> Any:
        if timeout_ms <= 0:
            raise ValueError("MCP timeout_ms must be greater than zero.")
        if not method.strip():
            raise ValueError("MCP method cannot be empty.")

        def run():
            return asyncio.run(self._request(method.strip(), dict(params), timeout_ms))

        # Some synchronous RKJO adapters are called from an async host.
        # Never nest asyncio.run in that host's event loop.
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return run()
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(run).result()

    async def _request(self, method: str, params: dict[str, Any], timeout_ms: int) -> Any:
        try:
            import anyio
            from pydantic import TypeAdapter
            from mcp import ClientSession, StdioServerParameters, types
            from mcp.client.stdio import stdio_client
        except ImportError as exc:
            raise MCPTransportError("Install rkjo-kernel[mcp] to use stdio MCP.") from exc

        try:
            with anyio.fail_after(timeout_ms / 1000):
                # SDK default environment avoids forwarding all host secrets.
                server = StdioServerParameters(command=self.command, args=self.args,
                                               env=self.env, cwd=self.cwd)
                with open(os.devnull, "w") as errlog:
                    async with stdio_client(server, errlog=errlog) as (reader, writer):
                        async with ClientSession(
                            reader, writer, read_timeout_seconds=timeout_ms / 1000,
                            client_info=types.Implementation(name=self.client_name, version=self.client_version),
                        ) as session:
                            await session.initialize()
                            result = await session.send_request(
                                TypeAdapter(types.ClientRequest).validate_python({"method": method, "params": params}),
                                TypeAdapter(dict[str, Any]),
                            )
                            return result
        except TimeoutError:
            raise MCPTransportTimeoutError(f"MCP stdio request timed out after {timeout_ms} ms.") from None
        except Exception:
            # Remote errors/stderr may include credentials or document content.
            raise MCPTransportError("MCP stdio session failed.") from None
