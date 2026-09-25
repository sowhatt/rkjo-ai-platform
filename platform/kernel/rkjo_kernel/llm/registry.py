"""Provider registry for RKJO LLM adapters."""

from __future__ import annotations

from rkjo_kernel.llm.port import LLMPort
from rkjo_kernel.llm.provider import (
    LLMProviderDescriptor,
)


class LLMProviderRegistry:
    """Register and resolve LLM providers."""

    def __init__(self) -> None:
        self._providers: dict[
            str,
            LLMProviderDescriptor,
        ] = {}

    def register(
        self,
        name: str,
        provider: LLMPort,
        *,
        is_local: bool = False,
        supports_streaming: bool = False,
    ) -> None:
        descriptor = LLMProviderDescriptor(
            name=name,
            adapter=provider,
            is_local=is_local,
            supports_streaming=supports_streaming,
        )

        if descriptor.name in self._providers:
            raise ValueError(
                "LLM provider already registered: "
                f"{descriptor.name}"
            )

        self._providers[
            descriptor.name
        ] = descriptor

    def get(
        self,
        name: str,
    ) -> LLMPort:
        return self.describe(name).adapter

    def describe(
        self,
        name: str,
    ) -> LLMProviderDescriptor:
        normalized = name.strip().lower()

        try:
            return self._providers[normalized]
        except KeyError as exc:
            raise KeyError(
                f"Unknown LLM provider: {normalized}"
            ) from exc

    def contains(
        self,
        name: str,
    ) -> bool:
        return (
            name.strip().lower()
            in self._providers
        )

    def names(self) -> tuple[str, ...]:
        return tuple(
            sorted(self._providers)
        )
