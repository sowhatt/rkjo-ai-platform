"""Grounded RAG answer generation backed by the RKJO LLM port."""

from __future__ import annotations

from rkjo_kernel.llm.models import (
    LLMMessage,
    LLMRequest,
)
from rkjo_kernel.llm.port import LLMPort
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


class LLMBackedAnswerGenerator(AnswerGenerator):
    """Adapt the provider-neutral LLM port to the RAG AnswerGenerator contract."""

    def __init__(
        self,
        *,
        llm: LLMPort,
        model: str | None = None,
    ) -> None:
        if model is not None and not model.strip():
            raise ValueError("model must not be empty.")

        self.llm = llm
        self.model = model

    def generate(
        self,
        *,
        question: str,
        context: str,
    ) -> str:
        if not question.strip():
            raise ValueError("question must not be empty.")

        if not context.strip():
            raise ValueError("context must not be empty.")

        response = self.llm.generate(
            LLMRequest(
                messages=(
                    LLMMessage(
                        role="system",
                        content=SYSTEM_PROMPT,
                    ),
                    LLMMessage(
                        role="user",
                        content=(
                            "QUESTION:\n"
                            f"{question}\n\n"
                            "CONTEXT:\n"
                            f"{context}"
                        ),
                    ),
                ),
                model=self.model,
                metadata={
                    "workload": "rag_answer_generation",
                },
            )
        )

        return response.content
