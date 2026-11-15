import pytest

from rkjo_kernel.llm.budget import (
    LLMBudget,
    LLMBudgetResolver,
)
from rkjo_kernel.mission.execution_context import (
    ExecutionContext,
)


def test_budget_resolver_reads_execution_context():
    context = ExecutionContext(
        mission_id="mission-1",
        tenant_id="tenant-1",
        budget={
            "llm": {
                "max_input_tokens": 10000,
                "max_output_tokens": 2000,
                "max_total_tokens": 12000,
                "max_cost": 0.50,
                "currency": "eur",
            }
        },
    )

    budget = LLMBudgetResolver().resolve(
        context
    )

    assert budget.max_input_tokens == 10000
    assert budget.max_output_tokens == 2000
    assert budget.max_total_tokens == 12000
    assert budget.max_cost == 0.50
    assert budget.currency == "EUR"


def test_budget_resolver_uses_defaults():
    context = ExecutionContext(
        mission_id="mission-1",
    )

    budget = LLMBudgetResolver().resolve(
        context
    )

    assert budget.max_input_tokens is None
    assert budget.max_output_tokens is None
    assert budget.max_total_tokens is None
    assert budget.max_cost is None
    assert budget.currency == "USD"


def test_budget_rejects_negative_limit():
    with pytest.raises(
        ValueError,
        match="max_total_tokens",
    ):
        LLMBudget(
            max_total_tokens=-1
        )


def test_budget_resolver_rejects_invalid_mapping():
    context = ExecutionContext(
        mission_id="mission-1",
        budget={
            "llm": "invalid",
        },
    )

    with pytest.raises(
        ValueError,
        match="must be a mapping",
    ):
        LLMBudgetResolver().resolve(
            context
        )


def test_budget_rejects_boolean_as_integer():
    context = ExecutionContext(
        mission_id="mission-1",
        budget={
            "llm": {
                "max_total_tokens": True,
            }
        },
    )

    with pytest.raises(
        ValueError,
        match="must be an integer",
    ):
        LLMBudgetResolver().resolve(
            context
        )
