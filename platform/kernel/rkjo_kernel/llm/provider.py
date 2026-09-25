"""Metadata describing an RKJO LLM provider."""

from __future__ import annotations

from dataclasses import dataclass

from rkjo_kernel.llm.port import LLMPort


@dataclass(frozen=True, slots=True)
class LLMProviderDescriptor:
    """One registered LLM provider and its execution properties."""

    name: str
    adapter: LLMPort
    is_local: bool = False
    supports_streaming: bool = False

    def __post_init__(self) -> None:
        normalized = self.name.strip().lower()

        if not normalized:
            raise ValueError(
                "Provider name must not be empty."
            )

        object.__setattr__(
            self,
            "name",
            normalized,
        )
