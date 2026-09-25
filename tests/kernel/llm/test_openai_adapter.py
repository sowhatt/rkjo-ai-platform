from types import SimpleNamespace

from rkjo_kernel.llm.models import (
    LLMMessage,
    LLMRequest,
)
from rkjo_kernel.llm.openai_adapter import (
    OpenAILLMAdapter,
)


class FakeResponses:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs

        return SimpleNamespace(
            output_text="Generated answer",
            usage=SimpleNamespace(
                input_tokens=12,
                output_tokens=7,
            ),
        )


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


def test_openai_adapter_generates_neutral_response():
    client = FakeClient()

    adapter = OpenAILLMAdapter(
        api_key="test-key",
        default_model="test-model",
        client=client,
    )

    result = adapter.generate(
        LLMRequest(
            messages=(
                LLMMessage(
                    role="system",
                    content="Use supplied context.",
                ),
                LLMMessage(
                    role="user",
                    content="What is RKJO?",
                ),
            ),
            tenant_id="tenant-1",
            trace_id="trace-1",
        )
    )

    assert result.content == "Generated answer"
    assert result.provider == "openai"
    assert result.model == "test-model"

    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 7
    assert result.usage.total_tokens == 19

    assert (
        client.responses.kwargs["instructions"]
        == "Use supplied context."
    )

    assert (
        "What is RKJO?"
        in client.responses.kwargs["input"]
    )

    assert client.responses.kwargs["store"] is False

    assert result.metadata["tenant_id"] == "tenant-1"
    assert result.metadata["trace_id"] == "trace-1"
