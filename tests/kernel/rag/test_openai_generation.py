from types import SimpleNamespace

import pytest

from rkjo_kernel.rag.openai_generation import (
    OpenAIAnswerGenerator,
)


class FakeResponses:
    def __init__(self, output_text):
        self.output_text = output_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)

        return SimpleNamespace(
            output_text=self.output_text
        )


class FakeClient:
    def __init__(self, output_text):
        self.responses = FakeResponses(
            output_text
        )


def test_openai_generator_uses_supplied_context():
    client = FakeClient(
        "Réponse fondée [1]."
    )

    generator = OpenAIAnswerGenerator(
        api_key="test-key",
        model="test-model",
        client=client,
    )

    answer = generator.generate(
        question="Question ?",
        context="[1]\nSource fiable.",
    )

    assert answer == "Réponse fondée [1]."

    call = client.responses.calls[0]

    assert call["model"] == "test-model"
    assert "Question ?" in call["input"]
    assert "Source fiable." in call["input"]


def test_openai_generator_rejects_empty_output():
    generator = OpenAIAnswerGenerator(
        api_key="test-key",
        client=FakeClient("   "),
    )

    with pytest.raises(RuntimeError):
        generator.generate(
            question="Question",
            context="[1] source",
        )


def test_openai_generator_disables_response_storage():
    client = FakeClient(
        "Réponse fondée [1]."
    )

    generator = OpenAIAnswerGenerator(
        api_key="test-key",
        model="test-model",
        client=client,
    )

    generator.generate(
        question="Question",
        context="[1] source",
    )

    call = client.responses.calls[0]

    assert call["store"] is False
