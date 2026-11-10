"""Provider-neutral models for RKJO LLM execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class LLMMessage:
    role: str
    content: str

    def __post_init__(self) -> None:
        normalized_role = self.role.strip().lower()

        if normalized_role not in {
            "system",
            "user",
            "assistant",
        }:
            raise ValueError(
                "LLMMessage role must be system, user, or assistant."
            )

        if not self.content.strip():
            raise ValueError(
                "LLMMessage content must not be empty."
            )

        object.__setattr__(self, "role", normalized_role)


@dataclass(frozen=True, slots=True)
class LLMRequest:
    messages: tuple[LLMMessage, ...]
    model: str | None = None
    tenant_id: str | None = None
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.messages:
            raise ValueError(
                "LLMRequest messages must not be empty."
            )

        if self.model is not None and not self.model.strip():
            raise ValueError(
                "LLMRequest model must not be empty."
            )


@dataclass(frozen=True, slots=True)
class LLMUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    def __post_init__(self) -> None:
        if self.input_tokens < 0:
            raise ValueError(
                "input_tokens must not be negative."
            )

        if self.output_tokens < 0:
            raise ValueError(
                "output_tokens must not be negative."
            )

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class LLMResponse:
    content: str
    provider: str
    model: str
    usage: LLMUsage = field(default_factory=LLMUsage)
    latency_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError(
                "LLMResponse content must not be empty."
            )

        if not self.provider.strip():
            raise ValueError(
                "LLMResponse provider must not be empty."
            )

        if not self.model.strip():
            raise ValueError(
                "LLMResponse model must not be empty."
            )

        if self.latency_ms < 0:
            raise ValueError(
                "latency_ms must not be negative."
            )
