import json
import subprocess

import pytest

from rkjo_kernel.tools.mcp.stdio_transport import StdioMCPTransport
from rkjo_kernel.tools.mcp.transport import (
    MCPTransportError,
    MCPTransportTimeoutError,
)


def test_stdio_transport_executes_json_rpc_request(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        body = json.loads(kwargs["input"])
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "result": {"tools": []},
                }
            )
            + "\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    transport = StdioMCPTransport(
        command="python",
        args=["server.py"],
        env={"MCP_TEST": "1"},
        client_name="rkjo-tests",
        client_version="2.0.0",
    )

    result = transport.request(
        method="tools/list",
        params={},
        headers={"Authorization": "ignored-for-stdio"},
        timeout_ms=1500,
    )

    payload = json.loads(captured["input"])
    assert captured["command"] == ["python", "server.py"]
    assert captured["timeout"] == 1.5
    assert captured["env"]["MCP_TEST"] == "1"
    assert payload["method"] == "tools/list"
    assert payload["params"]["_meta"]["io.modelcontextprotocol/clientInfo"] == {
        "name": "rkjo-tests",
        "version": "2.0.0",
    }
    assert result == {"tools": []}


def test_stdio_transport_maps_timeout(monkeypatch):
    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", fake_run)

    transport = StdioMCPTransport(command="python")

    with pytest.raises(MCPTransportTimeoutError):
        transport.request(
            method="tools/list",
            params={},
            headers={},
            timeout_ms=10,
        )


def test_stdio_transport_maps_process_failure_without_stderr_leak(monkeypatch):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(
            args=command,
            returncode=7,
            stdout="",
            stderr="secret-token-value",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    transport = StdioMCPTransport(command="python")

    with pytest.raises(MCPTransportError, match="exited with code 7") as exc_info:
        transport.request(
            method="tools/list",
            params={},
            headers={},
            timeout_ms=1000,
        )

    assert "secret-token-value" not in str(exc_info.value)


def test_stdio_transport_maps_json_rpc_error(monkeypatch):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {
                        "code": -32601,
                        "message": "Method not found",
                    },
                }
            )
            + "\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(MCPTransportError, match="-32601: Method not found"):
        StdioMCPTransport(command="python").request(
            method="tools/list",
            params={},
            headers={},
            timeout_ms=1000,
        )
