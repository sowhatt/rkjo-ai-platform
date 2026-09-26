"""Ollama adapter for the RKJO LLM port."""

from __future__ import annotations

from time import perf_counter
from typing import Any

import httpx

from rkjo_kernel.llm.models import (
    LLMRequest,
    LLMResponse,
    LLMUsage,
)


class OllamaLLMAdapter:
    """Execute provider-neutral LLM requests through the Ollama HTTP API."""

    provider = "ollama"

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        default_model: str = "qwen3:8b",
        timeout_seconds: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        normalized_url = base_url.strip().rstrip("/")

        if not normalized_url:
            raise ValueError("base_url must not be empty.")

        if not default_model.strip():
            raise ValueError("default_model must not be empty.")

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than 0."
            )

        self.base_url = normalized_url
        self.default_model = default_model.strip()
        self.client = client or httpx.Client(
            base_url=self.base_url,
            timeout=timeout_seconds,
        )

    def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        model = request.model or self.default_model

        payload: dict[str, Any] = {
            "model": model,
            "stream": False,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                }
                for message in request.messages
            ],
        }

        started = perf_counter()

        response = self.client.post(
            "/api/chat",
            json=payload,
        )
        response.raise_for_status()

        latency_ms = int(
            (perf_counter() - started) * 1000
        )

        body = response.json()
        message = body.get("message") or {}
        content = str(
            message.get("content") or ""
        ).strip()

        if not content:
            raise RuntimeError(
                "Ollama returned empty output."
            )

        return LLMResponse(
            content=content,
            provider=self.provider,
            model=str(
                body.get("model") or model
            ),
            usage=LLMUsage(
                input_tokens=self._token_count(
                    body,
                    "prompt_eval_count",
                ),
                output_tokens=self._token_count(
                    body,
                    "eval_count",
                ),
            ),
            latency_ms=latency_ms,
            metadata={
                "trace_id": request.trace_id,
                "tenant_id": request.tenant_id,
                "base_url": self.base_url,
            },
        )

    @staticmethod
    def _token_count(
        body: dict[str, Any],
        field_name: str,
    ) -> int:
        value = body.get(field_name, 0)

        if isinstance(value, bool):
            return 0

        if isinstance(value, int) and value >= 0:
            return value

        return 0
