"""Grounded RAG answer generation backed by the RKJO LLM port."""

from __future__ import annotations

from rkjo_kernel.llm.models import (
    LLMMessage,
    LLMRequest,
)
from rkjo_kernel.llm.gateway import LLMGateway
from rkjo_kernel.llm.port import LLMPort
from rkjo_kernel.mission.execution_context import ExecutionContext
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
        llm: LLMPort | None = None,
        gateway: LLMGateway | None = None,
        model: str | None = None,
        context_runtime=None,
    ) -> None:
        if (llm is None) == (gateway is None):
            raise ValueError(
                "Exactly one of llm or gateway must be provided."
            )

        if model is not None and not model.strip():
            raise ValueError("model must not be empty.")

        self.context_runtime = context_runtime
        self.llm = llm
        self.gateway = gateway
        self.model = model

    def generate(
        self,
        *,
        question: str,
        context: str,
        execution_context: ExecutionContext | None = None,
    ) -> str:
        if not question.strip():
            raise ValueError("question must not be empty.")

        if not context.strip():
            raise ValueError("context must not be empty.")

        request = LLMRequest(
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

        if self.gateway is not None:
            if execution_context is None:
                raise ValueError(
                    "execution_context is required when using LLMGateway."
                )
            if self.context_runtime is not None:
                from rkjo_kernel.runtime.context_runtime import RuntimeContextRequest
                from rkjo_kernel.memory import ContextBudget
                from rkjo_kernel.memory.llm_context_adapter import LLMContextAdapter
                package = self.context_runtime.prepare(
                    execution_context=execution_context,
                    request=RuntimeContextRequest(budget=ContextBudget(max_items=12, max_characters=5000)),
                )
                request = LLMContextAdapter().prepare(request, context=execution_context, package=package)
            response = self.gateway.generate(
                request,
                context=execution_context,
            )
        else:
            assert self.llm is not None
            response = self.llm.generate(request)

        return response.content
