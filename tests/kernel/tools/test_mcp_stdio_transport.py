"""Exercise real subprocess boundaries, not subprocess.run mocks."""
import asyncio
import sys
from pathlib import Path

import pytest

from rkjo_kernel.tools.mcp.stdio_transport import StdioMCPTransport
from rkjo_kernel.tools.mcp.transport import MCPTransportError, MCPTransportTimeoutError

SERVER = Path(__file__).resolve().parents[2] / "fixtures/mcp/real_course_server.py"


def transport():
    return StdioMCPTransport(command=sys.executable, args=[str(SERVER)])


def test_initialized_session_lists_and_calls_real_tool():
    t = transport()
    listed = t.request(method="tools/list", params={}, headers={}, timeout_ms=10000)
    assert [item["name"] for item in listed["tools"]] == ["search_courses"]
    result = t.request(method="tools/call", params={"name": "search_courses", "arguments": {"query": "Biotechnology"}}, headers={}, timeout_ms=10000)
    assert "Biotechnology Fundamentals" in str(result)


def test_sync_transport_can_be_used_from_async_host():
    async def host():
        return transport().request(method="tools/list", params={}, headers={}, timeout_ms=10000)
    assert asyncio.run(host())["tools"][0]["name"] == "search_courses"


def test_stdio_transport_maps_timeout():
    t = StdioMCPTransport(command=sys.executable, args=["-c", "import time; time.sleep(30)"])
    with pytest.raises(MCPTransportTimeoutError):
        t.request(method="tools/list", params={}, headers={}, timeout_ms=100)


def test_stdio_transport_does_not_leak_stderr():
    t = StdioMCPTransport(command=sys.executable, args=["-c", "import sys; sys.stderr.write('secret-token-value'); sys.exit(7)"])
    with pytest.raises(MCPTransportError) as error:
        t.request(method="tools/list", params={}, headers={}, timeout_ms=1000)
    assert "secret-token-value" not in str(error.value)


def test_stdio_transport_rejects_remote_protocol_error():
    with pytest.raises(MCPTransportError):
        transport().request(method="tools/call", params={}, headers={}, timeout_ms=10000)
