"""Policy-aware RKJO LLM router."""

from __future__ import annotations

from rkjo_kernel.llm.models import (
    LLMRequest,
    LLMResponse,
)
from rkjo_kernel.llm.policy import (
    LLMRoutingPolicy,
)
from rkjo_kernel.llm.provider import (
    LLMProviderDescriptor,
)
from rkjo_kernel.llm.registry import (
    LLMProviderRegistry,
)


class LLMRoutingError(RuntimeError):
    """No permitted provider could complete the request."""


class LLMRouter:
    """Route requests without depending on provider SDKs."""

    def __init__(
        self,
        *,
        registry: LLMProviderRegistry,
        default_provider: str,
    ) -> None:
        normalized = (
            default_provider
            .strip()
            .lower()
        )

        if not normalized:
            raise ValueError(
                "default_provider must not be empty."
            )

        self.registry = registry
        self.default_provider = normalized

    def generate(
        self,
        request: LLMRequest,
        *,
        policy: LLMRoutingPolicy | None = None,
    ) -> LLMResponse:
        active_policy = (
            policy
            or LLMRoutingPolicy()
        )

        failed: list[str] = []

        for provider_name in self._candidates(
            active_policy
        ):
            if not self.registry.contains(
                provider_name
            ):
                continue

            descriptor = (
                self.registry.describe(
                    provider_name
                )
            )

            if not self._permitted(
                descriptor,
                active_policy,
            ):
                continue

            try:
                response = (
                    descriptor.adapter.generate(
                        request
                    )
                )
            except Exception:
                failed.append(
                    provider_name
                )
                continue

            metadata = dict(
                response.metadata
            )

            metadata.update(
                {
                    "routed_provider": (
                        provider_name
                    ),
                    "route_failures": tuple(
                        failed
                    ),
                    "local_execution": (
                        descriptor.is_local
                    ),
                }
            )

            return LLMResponse(
                content=response.content,
                provider=response.provider,
                model=response.model,
                usage=response.usage,
                latency_ms=response.latency_ms,
                metadata=metadata,
            )

        raise LLMRoutingError(
            "No permitted LLM provider "
            "completed the request."
        )

    def _permitted(
        self,
        descriptor: LLMProviderDescriptor,
        policy: LLMRoutingPolicy,
    ) -> bool:
        if not policy.permits_name(
            descriptor.name
        ):
            return False

        if (
            policy.require_local_model
            and not descriptor.is_local
        ):
            return False

        if (
            not policy.allow_external_processing
            and not descriptor.is_local
        ):
            return False

        return True

    def _candidates(
        self,
        policy: LLMRoutingPolicy,
    ) -> tuple[str, ...]:
        result: list[str] = []

        for name in (
            self.default_provider,
            *policy.fallback_chain,
        ):
            normalized = (
                name.strip().lower()
            )

            if normalized not in result:
                result.append(normalized)

        return tuple(result)
