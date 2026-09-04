"""Synchronous MCP stdio transport using Python's standard library."""

from __future__ import annotations

import json
import os
import subprocess
from itertools import count
from typing import Any, Mapping

from rkjo_kernel.tools.mcp.transport import (
    MCPTransport,
    MCPTransportError,
    MCPTransportTimeoutError,
)


class StdioMCPTransport(MCPTransport):
    """Execute MCP JSON-RPC requests against a stdio subprocess.

    V1 intentionally uses one subprocess per request. This keeps the kernel
    stateless and deterministic; a persistent session transport can be added
    later behind the same MCPTransport contract.
    """

    def __init__(
        self,
        *,
        command: str,
        args: list[str] | None = None,
        env: Mapping[str, str] | None = None,
        cwd: str | None = None,
        client_name: str = "rkjo-ai-platform",
        client_version: str = "1.0.0",
    ) -> None:
        normalized_command = command.strip()
        if not normalized_command:
            raise ValueError("MCP stdio command cannot be empty.")

        self.command = normalized_command
        self.args = list(args or [])
        self.env = dict(env or {})
        self.cwd = cwd
        self.client_name = client_name.strip() or "rkjo-ai-platform"
        self.client_version = client_version.strip() or "1.0.0"
        self._request_ids = count(1)

    def request(
        self,
        *,
        method: str,
        params: dict[str, Any],
        headers: dict[str, str],
        timeout_ms: int,
    ) -> Any:
        if timeout_ms <= 0:
            raise ValueError("MCP timeout_ms must be greater than zero.")

        normalized_method = method.strip()
        if not normalized_method:
            raise ValueError("MCP method cannot be empty.")

        request_params = dict(params)
        meta = request_params.get("_meta")
        request_meta = dict(meta) if isinstance(meta, dict) else {}
        request_meta.setdefault(
            "io.modelcontextprotocol/clientInfo",
            {
                "name": self.client_name,
                "version": self.client_version,
            },
        )
        request_params["_meta"] = request_meta

        envelope = {
            "jsonrpc": "2.0",
            "id": next(self._request_ids),
            "method": normalized_method,
            "params": request_params,
        }

        process_env = os.environ.copy()
        process_env.update(self.env)

        try:
            completed = subprocess.run(
                [self.command, *self.args],
                input=json.dumps(envelope) + "\n",
                capture_output=True,
                text=True,
                cwd=self.cwd,
                env=process_env,
                timeout=timeout_ms / 1000,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise MCPTransportTimeoutError(
                f"MCP stdio request timed out after {timeout_ms} ms."
            ) from exc
        except OSError as exc:
            raise MCPTransportError("MCP stdio process could not be started.") from exc

        if completed.returncode != 0:
            raise MCPTransportError(
                f"MCP stdio process exited with code {completed.returncode}."
            )

        response_line = self._last_json_line(completed.stdout)
        if response_line is None:
            raise MCPTransportError("MCP stdio process returned no JSON response.")

        try:
            response = json.loads(response_line)
        except json.JSONDecodeError as exc:
            raise MCPTransportError("MCP stdio response is not valid JSON.") from exc

        if not isinstance(response, dict):
            raise MCPTransportError("MCP stdio response must be a JSON object.")

        if "error" in response:
            error = response["error"]
            code = error.get("code") if isinstance(error, dict) else None
            message = error.get("message") if isinstance(error, dict) else None
            detail = message or "remote MCP error"
            if code is not None:
                detail = f"{code}: {detail}"
            raise MCPTransportError(f"MCP server returned {detail}.")

        if "result" not in response:
            raise MCPTransportError("MCP stdio response has no result field.")

        return response["result"]

    @staticmethod
    def _last_json_line(stdout: str) -> str | None:
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        return lines[-1] if lines else None
