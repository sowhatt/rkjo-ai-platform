import pytest

from rkjo_kernel.llm.gateway import (
    LLMBudgetExceededError,
    LLMGateway,
)
from rkjo_kernel.llm.models import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMUsage,
)
from rkjo_kernel.llm.registry import (
    LLMProviderRegistry,
)
from rkjo_kernel.llm.router import LLMRouter
from rkjo_kernel.mission.execution_context import (
    ExecutionContext,
)


class CapturingProvider:
    def __init__(
        self,
        name: str,
        *,
        usage: LLMUsage | None = None,
    ):
        self.name = name
        self.usage = usage or LLMUsage()
        self.requests = []

    def generate(self, request):
        self.requests.append(request)

        return LLMResponse(
            content="ok",
            provider=self.name,
            model=f"{self.name}-model",
            usage=self.usage,
        )


def request():
    return LLMRequest(
        messages=(
            LLMMessage(
                role="user",
                content="Hello",
            ),
        ),
    )


def test_gateway_propagates_execution_context():
    registry = LLMProviderRegistry()
    provider = CapturingProvider("openai")
    registry.register("openai", provider)

    gateway = LLMGateway(
        router=LLMRouter(
            registry=registry,
            default_provider="openai",
        )
    )

    context = ExecutionContext(
        mission_id="mission-1",
        tenant_id="tenant-1",
        trace_id="trace-1",
    )

    gateway.generate(
        request(),
        context=context,
    )

    sent = provider.requests[0]

    assert sent.tenant_id == "tenant-1"
    assert sent.trace_id == "trace-1"
    assert sent.metadata["mission_id"] == "mission-1"
    assert sent.metadata["tenant_id"] == "tenant-1"


def test_gateway_applies_local_policy_from_context():
    registry = LLMProviderRegistry()
    cloud = CapturingProvider("openai")
    local = CapturingProvider("ollama")

    registry.register("openai", cloud)
    registry.register(
        "ollama",
        local,
        is_local=True,
    )

    gateway = LLMGateway(
        router=LLMRouter(
            registry=registry,
            default_provider="openai",
        )
    )

    context = ExecutionContext(
        mission_id="mission-1",
        policy_context={
            "llm": {
                "fallback_chain": ["ollama"],
                "allow_external_processing": False,
            }
        },
    )

    response = gateway.generate(
        request(),
        context=context,
    )

    assert response.provider == "ollama"
    assert len(cloud.requests) == 0
    assert len(local.requests) == 1


def test_gateway_enforces_total_token_budget():
    registry = LLMProviderRegistry()
    provider = CapturingProvider(
        "openai",
        usage=LLMUsage(
            input_tokens=80,
            output_tokens=30,
        ),
    )
    registry.register("openai", provider)

    gateway = LLMGateway(
        router=LLMRouter(
            registry=registry,
            default_provider="openai",
        )
    )

    context = ExecutionContext(
        mission_id="mission-1",
        budget={
            "llm": {
                "max_total_tokens": 100,
            }
        },
    )

    with pytest.raises(
        LLMBudgetExceededError,
        match="total token",
    ):
        gateway.generate(
            request(),
            context=context,
        )
