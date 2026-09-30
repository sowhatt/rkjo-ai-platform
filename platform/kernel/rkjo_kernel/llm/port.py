"""Provider-neutral LLM contract."""

from __future__ import annotations

from typing import Protocol

from rkjo_kernel.llm.models import (
    LLMRequest,
    LLMResponse,
)


class LLMPort(Protocol):
    """Execute an LLM request without exposing provider APIs."""

    def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        ...
