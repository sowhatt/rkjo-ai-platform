import pytest

from rkjo_kernel.llm.models import (
    LLMResponse,
)
from rkjo_kernel.llm.registry import (
    LLMProviderRegistry,
)


class FakeProvider:
    def generate(self, request):
        return LLMResponse(
            content="ok",
            provider="fake",
            model="fake-model",
        )


def test_registry_registers_and_resolves_provider():
    registry = LLMProviderRegistry()
    provider = FakeProvider()

    registry.register("OpenAI", provider)

    assert registry.get("openai") is provider
    assert registry.contains("OPENAI")
    assert registry.names() == ("openai",)


def test_registry_rejects_duplicate_provider():
    registry = LLMProviderRegistry()
    provider = FakeProvider()

    registry.register("openai", provider)

    with pytest.raises(
        ValueError,
        match="already registered",
    ):
        registry.register("OPENAI", provider)


def test_registry_rejects_unknown_provider():
    registry = LLMProviderRegistry()

    with pytest.raises(
        KeyError,
        match="Unknown LLM provider",
    ):
        registry.get("deepseek")
