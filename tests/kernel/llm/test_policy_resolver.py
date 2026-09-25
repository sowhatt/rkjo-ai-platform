import pytest

from rkjo_kernel.llm.policy_resolver import (
    LLMPolicyResolver,
)
from rkjo_kernel.mission.execution_context import (
    ExecutionContext,
)


def test_resolver_builds_policy_from_execution_context():
    context = ExecutionContext(
        mission_id="mission-1",
        tenant_id="tenant-1",
        policy_context={
            "llm": {
                "allowed_providers": [
                    "OpenAI",
                    "OLLAMA",
                ],
                "fallback_chain": [
                    "ollama",
                ],
                "allow_external_processing": False,
                "require_local_model": True,
            }
        },
    )

    policy = LLMPolicyResolver().resolve(
        context
    )

    assert policy.allowed_providers == (
        "openai",
        "ollama",
    )

    assert policy.fallback_chain == (
        "ollama",
    )

    assert (
        policy.allow_external_processing
        is False
    )

    assert policy.require_local_model is True


def test_resolver_uses_safe_defaults():
    context = ExecutionContext(
        mission_id="mission-1",
    )

    policy = LLMPolicyResolver().resolve(
        context
    )

    assert policy.allowed_providers == ()
    assert policy.fallback_chain == ()
    assert (
        policy.allow_external_processing
        is True
    )
    assert (
        policy.require_local_model
        is False
    )


def test_resolver_rejects_invalid_llm_policy():
    context = ExecutionContext(
        mission_id="mission-1",
        policy_context={
            "llm": "invalid",
        },
    )

    with pytest.raises(
        ValueError,
        match="must be a mapping",
    ):
        LLMPolicyResolver().resolve(
            context
        )
