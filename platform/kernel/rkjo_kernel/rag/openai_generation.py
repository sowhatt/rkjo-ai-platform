"""OpenAI grounded answer generation."""

from __future__ import annotations

from openai import OpenAI

from rkjo_kernel.rag.generation_models import (
    AnswerGenerator,
)


SYSTEM_PROMPT = """You are the grounded answer generator for RKJO AI Platform.

Answer using ONLY the supplied context.

Rules:
- Do not invent facts.
- Do not use knowledge outside the supplied context.
- Every factual statement supported by the context must include the relevant
  citation marker such as [1] or [2].
- Never create a citation number that does not exist in the supplied context.
- If the context does not contain enough information, explicitly say that the
  available sources do not provide enough information.
- Keep the answer concise and precise.
"""


class OpenAIAnswerGenerator(AnswerGenerator):
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-5-mini",
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        client: OpenAI | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError(
                "api_key must not be empty."
            )

        if not model.strip():
            raise ValueError(
                "model must not be empty."
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than 0."
            )

        if max_retries < 0:
            raise ValueError(
                "max_retries must not be negative."
            )

        self.model = model

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
        *,
        question: str,
        context: str,
    ) -> str:
        if not question.strip():
            raise ValueError(
                "question must not be empty."
            )

        if not context.strip():
            raise ValueError(
                "context must not be empty."
            )

        response = self.client.responses.create(
            model=self.model,
            instructions=SYSTEM_PROMPT,
            store=False,
            input=(
                "QUESTION:\n"
                f"{question}\n\n"
                "CONTEXT:\n"
                f"{context}"
            ),
        )

        answer = response.output_text.strip()

        if not answer:
            raise RuntimeError(
                "Answer provider returned empty output."
            )

        return answer
