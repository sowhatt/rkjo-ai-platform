"""Routing policy for RKJO LLM providers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LLMRoutingPolicy:
    """Governance constraints for one LLM execution."""

    allowed_providers: tuple[str, ...] = ()
    fallback_chain: tuple[str, ...] = ()
    allow_external_processing: bool = True
    require_local_model: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "allowed_providers",
            self._normalize(
                self.allowed_providers
            ),
        )

        object.__setattr__(
            self,
            "fallback_chain",
            self._normalize(
                self.fallback_chain
            ),
        )

    def permits_name(
        self,
        provider: str,
    ) -> bool:
        normalized = provider.strip().lower()

        if not normalized:
            return False

        if not self.allowed_providers:
            return True

        return (
            normalized
            in self.allowed_providers
        )

    @staticmethod
    def _normalize(
        values: tuple[str, ...],
    ) -> tuple[str, ...]:
        normalized: list[str] = []

        for value in values:
            item = value.strip().lower()

            if not item:
                raise ValueError(
                    "Provider names must not be empty."
                )

            if item not in normalized:
                normalized.append(item)

        return tuple(normalized)
