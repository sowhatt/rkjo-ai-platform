from types import SimpleNamespace

import pytest

from rkjo_kernel.llm.models import (
    LLMMessage,
    LLMRequest,
)
from rkjo_kernel.llm.ollama_adapter import (
    OllamaLLMAdapter,
)


class FakeResponse:
    def __init__(self, body):
        self.body = body
        self.raise_calls = 0

    def raise_for_status(self):
        self.raise_calls += 1

    def json(self):
        return self.body


class FakeClient:
    def __init__(self, body):
        self.response = FakeResponse(body)
        self.calls = []

    def post(self, path, *, json):
        self.calls.append(
            SimpleNamespace(
                path=path,
                json=json,
            )
        )
        return self.response


def make_request(model=None):
    return LLMRequest(
        messages=(
            LLMMessage(
                role="system",
                content="Stay grounded.",
            ),
            LLMMessage(
                role="user",
                content="Hello",
            ),
        ),
        model=model,
        tenant_id="tenant-1",
        trace_id="trace-1",
    )


def test_ollama_adapter_calls_chat_api():
    client = FakeClient(
        {
            "model": "qwen3:8b",
            "message": {
                "role": "assistant",
                "content": "Bonjour",
            },
            "prompt_eval_count": 12,
            "eval_count": 4,
        }
    )

    adapter = OllamaLLMAdapter(
        base_url="http://localhost:11434/",
        default_model="qwen3:8b",
        client=client,
    )

    result = adapter.generate(
        make_request()
    )

    call = client.calls[0]

    assert call.path == "/api/chat"
    assert call.json["model"] == "qwen3:8b"
    assert call.json["stream"] is False
    assert call.json["messages"] == [
        {
            "role": "system",
            "content": "Stay grounded.",
        },
        {
            "role": "user",
            "content": "Hello",
        },
    ]

    assert result.content == "Bonjour"
    assert result.provider == "ollama"
    assert result.model == "qwen3:8b"
    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 4
    assert result.metadata["tenant_id"] == "tenant-1"
    assert result.metadata["trace_id"] == "trace-1"
    assert (
        result.metadata["base_url"]
        == "http://localhost:11434"
    )
    assert client.response.raise_calls == 1


def test_ollama_adapter_allows_model_override():
    client = FakeClient(
        {
            "message": {
                "content": "ok",
            }
        }
    )

    adapter = OllamaLLMAdapter(
        default_model="qwen3:8b",
        client=client,
    )

    result = adapter.generate(
        make_request(
            model="llama3.2:3b"
        )
    )

    assert (
        client.calls[0].json["model"]
        == "llama3.2:3b"
    )
    assert result.model == "llama3.2:3b"


def test_ollama_adapter_rejects_empty_output():
    adapter = OllamaLLMAdapter(
        client=FakeClient(
            {
                "message": {
                    "content": "   ",
                }
            }
        )
    )

    with pytest.raises(
        RuntimeError,
        match="empty output",
    ):
        adapter.generate(
            make_request()
        )


def test_ollama_adapter_rejects_invalid_configuration():
    with pytest.raises(
        ValueError,
        match="base_url",
    ):
        OllamaLLMAdapter(
            base_url=" ",
        )

    with pytest.raises(
        ValueError,
        match="default_model",
    ):
        OllamaLLMAdapter(
            default_model=" ",
        )

    with pytest.raises(
        ValueError,
        match="timeout_seconds",
    ):
        OllamaLLMAdapter(
            timeout_seconds=0,
        )
