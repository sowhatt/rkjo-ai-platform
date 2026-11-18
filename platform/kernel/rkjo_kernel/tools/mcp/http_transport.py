"""Stateless MCP Streamable HTTP transport.

Implements the request/response subset needed by RKJO Tool Runtime using
Python's standard library only. The transport targets MCP protocol revision
2026-07-28 and intentionally keeps SSE/subscriptions outside the kernel V1.
"""

from __future__ import annotations

import json
import socket
from itertools import count
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from rkjo_kernel.tools.mcp.transport import (
    MCPTransport,
    MCPTransportError,
    MCPTransportTimeoutError,
)


UrlOpener = Callable[..., Any]


class HTTPMCPTransport(MCPTransport):
    """JSON-RPC MCP transport over stateless Streamable HTTP."""

    PROTOCOL_VERSION = "2026-07-28"

    def __init__(
        self,
        *,
        endpoint: str,
        client_name: str = "rkjo-ai-platform",
        client_version: str = "1.0.0",
        opener: UrlOpener | None = None,
    ) -> None:
        normalized_endpoint = endpoint.strip()
        parsed = urlparse(normalized_endpoint)

        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("MCP HTTP endpoint must be an absolute HTTP(S) URL.")

        if not client_name.strip():
            raise ValueError("MCP client_name cannot be empty.")

        if not client_version.strip():
            raise ValueError("MCP client_version cannot be empty.")

        self.endpoint = normalized_endpoint
        self.client_name = client_name.strip()
        self.client_version = client_version.strip()
        self._opener = opener or urlopen
        self._request_ids = count(1)

    def request(
        self,
        *,
        method: str,
        params: dict[str, Any],
        headers: dict[str, str],
        timeout_ms: int,
    ) -> Any:
        normalized_method = method.strip()

        if not normalized_method:
            raise ValueError("MCP method cannot be empty.")

        if timeout_ms <= 0:
            raise ValueError("MCP timeout_ms must be greater than zero.")

        request_params = dict(params)
        request_params["_meta"] = self._build_meta(request_params.get("_meta"))

        payload = {
            "jsonrpc": "2.0",
            "id": next(self._request_ids),
            "method": normalized_method,
            "params": request_params,
        }

        request_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "MCP-Protocol-Version": self.PROTOCOL_VERSION,
            "Mcp-Method": normalized_method,
            **headers,
        }

        route_name = self._route_name(normalized_method, request_params)
        if route_name is not None:
            request_headers["Mcp-Name"] = route_name

        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=request_headers,
            method="POST",
        )

        try:
            with self._opener(
                request,
                timeout=timeout_ms / 1000,
            ) as response:
                raw_body = response.read()
        except HTTPError as exc:
            raise MCPTransportError(
                f"MCP HTTP request failed with status {exc.code}."
            ) from exc
        except (socket.timeout, TimeoutError) as exc:
            raise MCPTransportTimeoutError(
                f"MCP HTTP request timed out after {timeout_ms} ms."
            ) from exc
        except URLError as exc:
            if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                raise MCPTransportTimeoutError(
                    f"MCP HTTP request timed out after {timeout_ms} ms."
                ) from exc

            raise MCPTransportError("MCP HTTP request failed.") from exc
        except OSError as exc:
            raise MCPTransportError("MCP HTTP request failed.") from exc

        try:
            envelope = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MCPTransportError(
                "MCP HTTP response is not valid JSON."
            ) from exc

        if not isinstance(envelope, dict):
            raise MCPTransportError("MCP HTTP response must be a JSON object.")

        if "error" in envelope:
            error = envelope["error"]
            code = error.get("code") if isinstance(error, dict) else None
            message = error.get("message") if isinstance(error, dict) else None
            detail = message or "remote MCP error"
            if code is not None:
                detail = f"{code}: {detail}"
            raise MCPTransportError(f"MCP server returned {detail}.")

        if "result" not in envelope:
            raise MCPTransportError("MCP HTTP response has no result field.")

        return envelope["result"]

    def _build_meta(self, existing_meta: Any) -> dict[str, Any]:
        meta = dict(existing_meta) if isinstance(existing_meta, dict) else {}
        meta.setdefault(
            "io.modelcontextprotocol/clientInfo",
            {
                "name": self.client_name,
                "version": self.client_version,
            },
        )
        return meta

    @staticmethod
    def _route_name(
        method: str,
        params: dict[str, Any],
    ) -> str | None:
        if method in {"tools/call", "prompts/get"}:
            name = params.get("name")
            return str(name) if name is not None else None

        if method == "resources/read":
            uri = params.get("uri")
            return str(uri) if uri is not None else None

        if method in {"tasks/get", "tasks/update", "tasks/cancel"}:
            task_id = params.get("taskId")
            return str(task_id) if task_id is not None else None

        return None
