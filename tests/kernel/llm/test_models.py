import pytest

from rkjo_kernel.llm.models import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMUsage,
)


def test_message_normalizes_role():
    message = LLMMessage(
        role=" USER ",
        content="Hello",
    )

    assert message.role == "user"


def test_message_rejects_unknown_role():
    with pytest.raises(ValueError, match="role"):
        LLMMessage(
            role="tool",
            content="Hello",
        )


def test_request_requires_messages():
    with pytest.raises(ValueError, match="messages"):
        LLMRequest(messages=())


def test_usage_computes_total_tokens():
    usage = LLMUsage(
        input_tokens=10,
        output_tokens=5,
    )

    assert usage.total_tokens == 15


def test_usage_rejects_negative_tokens():
    with pytest.raises(ValueError, match="input_tokens"):
        LLMUsage(input_tokens=-1)


def test_response_requires_provider():
    with pytest.raises(ValueError, match="provider"):
        LLMResponse(
            content="Hello",
            provider=" ",
            model="test-model",
        )
