"""Resolve LLM routing policy from RKJO execution context."""

from __future__ import annotations

from typing import Any

from rkjo_kernel.llm.policy import (
    LLMRoutingPolicy,
)
from rkjo_kernel.mission.execution_context import (
    ExecutionContext,
)


class LLMPolicyResolver:
    """Translate RKJO governance context into LLM routing rules."""

    def resolve(
        self,
        context: ExecutionContext,
    ) -> LLMRoutingPolicy:
        raw = context.policy_context.get(
            "llm",
            {},
        )

        if raw is None:
            raw = {}

        if not isinstance(raw, dict):
            raise ValueError(
                "policy_context['llm'] must be a mapping."
            )

        return LLMRoutingPolicy(
            allowed_providers=self._providers(
                raw.get(
                    "allowed_providers",
                    (),
                ),
                "allowed_providers",
            ),
            fallback_chain=self._providers(
                raw.get(
                    "fallback_chain",
                    (),
                ),
                "fallback_chain",
            ),
            allow_external_processing=self._boolean(
                raw.get(
                    "allow_external_processing",
                    True,
                ),
                "allow_external_processing",
            ),
            require_local_model=self._boolean(
                raw.get(
                    "require_local_model",
                    False,
                ),
                "require_local_model",
            ),
        )

    @staticmethod
    def _providers(
        value: Any,
        field_name: str,
    ) -> tuple[str, ...]:
        if value is None:
            return ()

        if not isinstance(
            value,
            (list, tuple),
        ):
            raise ValueError(
                f"{field_name} must be a list or tuple."
            )

        if not all(
            isinstance(item, str)
            for item in value
        ):
            raise ValueError(
                f"{field_name} must contain strings."
            )

        return tuple(value)

    @staticmethod
    def _boolean(
        value: Any,
        field_name: str,
    ) -> bool:
        if not isinstance(value, bool):
            raise ValueError(
                f"{field_name} must be a boolean."
            )

        return value
