import io
import json
import socket
from urllib.error import HTTPError, URLError

import pytest

from rkjo_kernel.tools.mcp.http_transport import HTTPMCPTransport
from rkjo_kernel.tools.mcp.transport import (
    MCPTransportError,
    MCPTransportTimeoutError,
)


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._body


def test_http_transport_sends_stateless_mcp_headers_and_meta():
    captured = {}

    def opener(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"content": [{"type": "text", "text": "ok"}]},
            }
        )

    transport = HTTPMCPTransport(
        endpoint="https://mcp.example.test/mcp",
        client_name="rkjo-tests",
        client_version="2.0.0",
        opener=opener,
    )

    result = transport.request(
        method="tools/call",
        params={
            "name": "search_courses",
            "arguments": {"query": "biotechnology"},
        },
        headers={"Authorization": "Bearer tenant-token"},
        timeout_ms=12_000,
    )

    request = captured["request"]
    body = json.loads(request.data.decode("utf-8"))
    headers = {key.lower(): value for key, value in request.header_items()}

    assert captured["timeout"] == 12.0
    assert headers["mcp-protocol-version"] == "2026-07-28"
    assert headers["mcp-method"] == "tools/call"
    assert headers["mcp-name"] == "search_courses"
    assert headers["authorization"] == "Bearer tenant-token"
    assert body["jsonrpc"] == "2.0"
    assert body["method"] == "tools/call"
    assert body["params"]["arguments"] == {"query": "biotechnology"}
    assert body["params"]["_meta"]["io.modelcontextprotocol/clientInfo"] == {
        "name": "rkjo-tests",
        "version": "2.0.0",
    }
    assert result["content"][0]["text"] == "ok"


def test_http_transport_maps_socket_timeout():
    def opener(request, timeout):
        raise socket.timeout("slow")

    transport = HTTPMCPTransport(
        endpoint="https://mcp.example.test/mcp",
        opener=opener,
    )

    with pytest.raises(MCPTransportTimeoutError):
        transport.request(
            method="tools/list",
            params={},
            headers={},
            timeout_ms=100,
        )


def test_http_transport_maps_url_timeout():
    def opener(request, timeout):
        raise URLError(socket.timeout("slow"))

    transport = HTTPMCPTransport(
        endpoint="https://mcp.example.test/mcp",
        opener=opener,
    )

    with pytest.raises(MCPTransportTimeoutError):
        transport.request(
            method="tools/list",
            params={},
            headers={},
            timeout_ms=100,
        )


def test_http_transport_maps_http_error_without_leaking_body():
    def opener(request, timeout):
        raise HTTPError(
            url=request.full_url,
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b"secret server body"),
        )

    transport = HTTPMCPTransport(
        endpoint="https://mcp.example.test/mcp",
        opener=opener,
    )

    with pytest.raises(MCPTransportError, match="status 401") as exc_info:
        transport.request(
            method="tools/list",
            params={},
            headers={"Authorization": "Bearer sensitive"},
            timeout_ms=1000,
        )

    assert "secret server body" not in str(exc_info.value)
    assert "sensitive" not in str(exc_info.value)


def test_http_transport_maps_json_rpc_error():
    def opener(request, timeout):
        return FakeResponse(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {
                    "code": -32601,
                    "message": "Method not found",
                },
            }
        )

    transport = HTTPMCPTransport(
        endpoint="https://mcp.example.test/mcp",
        opener=opener,
    )

    with pytest.raises(
        MCPTransportError,
        match="-32601: Method not found",
    ):
        transport.request(
            method="tools/list",
            params={},
            headers={},
            timeout_ms=1000,
        )


def test_http_transport_rejects_relative_endpoint():
    with pytest.raises(ValueError):
        HTTPMCPTransport(endpoint="/mcp")
