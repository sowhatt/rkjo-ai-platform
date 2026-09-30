"""OpenAI adapter for the RKJO LLM port."""

from __future__ import annotations

from time import perf_counter

from openai import OpenAI

from rkjo_kernel.llm.models import (
    LLMRequest,
    LLMResponse,
    LLMUsage,
)


class OpenAILLMAdapter:
    provider = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        default_model: str = "gpt-5-mini",
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        client: OpenAI | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError(
                "api_key must not be empty."
            )

        if not default_model.strip():
            raise ValueError(
                "default_model must not be empty."
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than 0."
            )

        if max_retries < 0:
            raise ValueError(
                "max_retries must not be negative."
            )

        self.default_model = default_model

        self.client = (
            client
            or OpenAI(
                api_key=api_key,
                timeout=timeout_seconds,
                max_retries=max_retries,
            )
        )

    def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        model = request.model or self.default_model

        instructions = "\n\n".join(
            message.content
            for message in request.messages
            if message.role == "system"
        )

        conversation = "\n\n".join(
            f"{message.role.upper()}:\n{message.content}"
            for message in request.messages
            if message.role != "system"
        )

        started = perf_counter()

        kwargs = {
            "model": model,
            "store": False,
            "input": conversation,
        }

        if instructions:
            kwargs["instructions"] = instructions

        response = self.client.responses.create(**kwargs)

        latency_ms = int(
            (perf_counter() - started) * 1000
        )

        content = response.output_text.strip()

        if not content:
            raise RuntimeError(
                "LLM provider returned empty output."
            )

        usage = getattr(response, "usage", None)

        input_tokens = (
            getattr(usage, "input_tokens", 0)
            if usage is not None
            else 0
        )

        output_tokens = (
            getattr(usage, "output_tokens", 0)
            if usage is not None
            else 0
        )

        return LLMResponse(
            content=content,
            provider=self.provider,
            model=model,
            usage=LLMUsage(
                input_tokens=input_tokens or 0,
                output_tokens=output_tokens or 0,
            ),
            latency_ms=latency_ms,
            metadata={
                "trace_id": request.trace_id,
                "tenant_id": request.tenant_id,
            },
        )
