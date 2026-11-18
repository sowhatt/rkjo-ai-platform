import pytest

from rkjo_kernel.llm.models import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
)
from rkjo_kernel.llm.policy import (
    LLMRoutingPolicy,
)
from rkjo_kernel.llm.registry import (
    LLMProviderRegistry,
)
from rkjo_kernel.llm.router import (
    LLMRouter,
    LLMRoutingError,
)


class FakeProvider:
    def __init__(
        self,
        name: str,
        *,
        fail: bool = False,
    ):
        self.name = name
        self.fail = fail
        self.calls = 0

    def generate(self, request):
        self.calls += 1

        if self.fail:
            raise RuntimeError(
                f"{self.name} unavailable"
            )

        return LLMResponse(
            content=f"{self.name} answer",
            provider=self.name,
            model=f"{self.name}-model",
        )


def make_request():
    return LLMRequest(
        messages=(
            LLMMessage(
                role="user",
                content="Hello",
            ),
        ),
        tenant_id="tenant-1",
        trace_id="trace-1",
    )


def test_router_uses_default_provider():
    registry = LLMProviderRegistry()
    openai = FakeProvider("openai")

    registry.register(
        "openai",
        openai,
    )

    router = LLMRouter(
        registry=registry,
        default_provider="openai",
    )

    result = router.generate(
        make_request()
    )

    assert result.provider == "openai"
    assert openai.calls == 1
    assert (
        result.metadata["local_execution"]
        is False
    )


def test_router_falls_back_after_failure():
    registry = LLMProviderRegistry()

    openai = FakeProvider(
        "openai",
        fail=True,
    )
    anthropic = FakeProvider(
        "anthropic"
    )

    registry.register(
        "openai",
        openai,
    )
    registry.register(
        "anthropic",
        anthropic,
    )

    router = LLMRouter(
        registry=registry,
        default_provider="openai",
    )

    result = router.generate(
        make_request(),
        policy=LLMRoutingPolicy(
            allowed_providers=(
                "openai",
                "anthropic",
            ),
            fallback_chain=(
                "anthropic",
            ),
        ),
    )

    assert result.provider == "anthropic"
    assert result.metadata[
        "route_failures"
    ] == ("openai",)


def test_policy_can_force_local_execution():
    registry = LLMProviderRegistry()

    openai = FakeProvider("openai")
    ollama = FakeProvider("ollama")

    registry.register(
        "openai",
        openai,
        is_local=False,
    )

    registry.register(
        "ollama",
        ollama,
        is_local=True,
    )

    router = LLMRouter(
        registry=registry,
        default_provider="openai",
    )

    result = router.generate(
        make_request(),
        policy=LLMRoutingPolicy(
            allowed_providers=(
                "openai",
                "ollama",
            ),
            fallback_chain=(
                "ollama",
            ),
            require_local_model=True,
        ),
    )

    assert result.provider == "ollama"
    assert openai.calls == 0
    assert ollama.calls == 1
    assert (
        result.metadata["local_execution"]
        is True
    )


def test_external_processing_can_be_forbidden():
    registry = LLMProviderRegistry()

    openai = FakeProvider("openai")
    ollama = FakeProvider("ollama")

    registry.register(
        "openai",
        openai,
    )

    registry.register(
        "ollama",
        ollama,
        is_local=True,
    )

    router = LLMRouter(
        registry=registry,
        default_provider="openai",
    )

    result = router.generate(
        make_request(),
        policy=LLMRoutingPolicy(
            fallback_chain=("ollama",),
            allow_external_processing=False,
        ),
    )

    assert result.provider == "ollama"
    assert openai.calls == 0


def test_router_fails_if_no_permitted_provider():
    registry = LLMProviderRegistry()

    registry.register(
        "openai",
        FakeProvider("openai"),
    )

    router = LLMRouter(
        registry=registry,
        default_provider="openai",
    )

    with pytest.raises(
        LLMRoutingError,
        match="No permitted",
    ):
        router.generate(
            make_request(),
            policy=LLMRoutingPolicy(
                require_local_model=True,
            ),
        )
