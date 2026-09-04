import pytest

from rkjo_kernel.tools.context import ToolExecutionContext
from rkjo_kernel.tools.mcp.credentials import MappingMCPCredentialProvider
from rkjo_kernel.tools.mcp.runtime_client import TransportMCPClient
from rkjo_kernel.tools.mcp.transport import MCPTransport


class FakeTransport(MCPTransport):
    def __init__(self) -> None:
        self.requests: list[dict] = []

    def request(
        self,
        *,
        method: str,
        params: dict,
        headers: dict[str, str],
        timeout_ms: int,
    ):
        self.requests.append(
            {
                "method": method,
                "params": params,
                "headers": headers,
                "timeout_ms": timeout_ms,
            }
        )

        if method == "tools/list":
            return {
                "tools": [
                    {
                        "name": "search_courses",
                        "description": "Search courses",
                        "inputSchema": {"type": "object"},
                    }
                ]
            }

        return {"content": [{"type": "text", "text": "ok"}]}


def test_transport_client_lists_tools():
    transport = FakeTransport()
    client = TransportMCPClient(
        transport=transport,
        server_name="education",
    )

    tools = client.list_tools()

    assert tools[0].name == "search_courses"
    assert tools[0].input_schema == {"type": "object"}
    assert transport.requests[0]["method"] == "tools/list"


def test_transport_client_uses_tenant_credentials_for_call():
    transport = FakeTransport()
    credentials = MappingMCPCredentialProvider(
        {
            ("tenant.demo", "education"): {
                "Authorization": "Bearer tenant-token",
            }
        }
    )
    client = TransportMCPClient(
        transport=transport,
        server_name="education",
        credential_provider=credentials,
        timeout_ms=12_000,
    )

    result = client.call_tool(
        tool_name="search_courses",
        arguments={"query": "biotechnology"},
        context=ToolExecutionContext(
            tenant_id="tenant.demo",
            agent_name="education.agent",
            capability_name="course_search",
        ),
    )

    request = transport.requests[0]
    assert request["method"] == "tools/call"
    assert request["params"] == {
        "name": "search_courses",
        "arguments": {"query": "biotechnology"},
    }
    assert request["headers"] == {
        "Authorization": "Bearer tenant-token"
    }
    assert request["timeout_ms"] == 12_000
    assert result["content"][0]["text"] == "ok"


def test_transport_client_fails_closed_without_context():
    client = TransportMCPClient(
        transport=FakeTransport(),
        server_name="education",
    )

    with pytest.raises(PermissionError):
        client.call_tool(
            tool_name="search_courses",
            arguments={},
        )


def test_transport_client_fails_closed_without_tenant_credentials():
    client = TransportMCPClient(
        transport=FakeTransport(),
        server_name="education",
        credential_provider=MappingMCPCredentialProvider({}),
    )

    with pytest.raises(PermissionError):
        client.call_tool(
            tool_name="search_courses",
            arguments={},
            context=ToolExecutionContext(
                tenant_id="tenant.missing",
                agent_name="education.agent",
                capability_name="course_search",
            ),
        )
