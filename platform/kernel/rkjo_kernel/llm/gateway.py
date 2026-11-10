"""Execution-context-aware LLM gateway for RKJO."""

from __future__ import annotations

from dataclasses import replace

from rkjo_kernel.llm.budget import (
    LLMBudget,
    LLMBudgetResolver,
)
from rkjo_kernel.llm.models import (
    LLMRequest,
    LLMResponse,
)
from rkjo_kernel.llm.policy_resolver import (
    LLMPolicyResolver,
)
from rkjo_kernel.llm.router import LLMRouter
from rkjo_kernel.mission.execution_context import (
    ExecutionContext,
)


class LLMBudgetExceededError(RuntimeError):
    """An LLM response exceeded an execution token budget."""


class LLMGateway:
    """Apply RKJO execution governance before and after LLM routing."""

    def __init__(
        self,
        *,
        router: LLMRouter,
        policy_resolver: LLMPolicyResolver | None = None,
        budget_resolver: LLMBudgetResolver | None = None,
    ) -> None:
        self.router = router
        self.policy_resolver = policy_resolver or LLMPolicyResolver()
        self.budget_resolver = budget_resolver or LLMBudgetResolver()

    def generate(
        self,
        request: LLMRequest,
        *,
        context: ExecutionContext,
    ) -> LLMResponse:
        self._validate_request_identity(request, context)
        policy = self.policy_resolver.resolve(context)
        budget = self.budget_resolver.resolve(context)

        metadata = dict(request.metadata)
        context.inject_into(metadata)

        governed_request = replace(
            request,
            tenant_id=context.tenant_id,
            trace_id=context.trace_id,
            metadata=metadata,
        )

        response = self.router.generate(
            governed_request,
            policy=policy,
        )

        self._enforce_usage(response, budget)
        return response

    @staticmethod
    def _validate_request_identity(
        request: LLMRequest,
        context: ExecutionContext,
    ) -> None:
        if (
            request.tenant_id is not None
            and request.tenant_id != context.tenant_id
        ):
            raise ValueError(
                "LLM request tenant_id conflicts with ExecutionContext"
            )
        if (
            request.trace_id is not None
            and request.trace_id != context.trace_id
        ):
            raise ValueError(
                "LLM request trace_id conflicts with ExecutionContext"
            )

    @staticmethod
    def _enforce_usage(
        response: LLMResponse,
        budget: LLMBudget,
    ) -> None:
        usage = response.usage

        if (
            budget.max_input_tokens is not None
            and usage.input_tokens > budget.max_input_tokens
        ):
            raise LLMBudgetExceededError(
                "LLM input token budget exceeded."
            )

        if (
            budget.max_output_tokens is not None
            and usage.output_tokens > budget.max_output_tokens
        ):
            raise LLMBudgetExceededError(
                "LLM output token budget exceeded."
            )

        if (
            budget.max_total_tokens is not None
            and usage.total_tokens > budget.max_total_tokens
        ):
            raise LLMBudgetExceededError(
                "LLM total token budget exceeded."
            )
