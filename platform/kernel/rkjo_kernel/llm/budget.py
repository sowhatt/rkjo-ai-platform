"""LLM budget constraints for RKJO executions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rkjo_kernel.mission.execution_context import (
    ExecutionContext,
)


@dataclass(frozen=True, slots=True)
class LLMBudget:
    """Limits applicable to one LLM execution path."""

    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_total_tokens: int | None = None
    max_cost: float | None = None
    currency: str = "USD"

    def __post_init__(self) -> None:
        for name in (
            "max_input_tokens",
            "max_output_tokens",
            "max_total_tokens",
        ):
            value = getattr(self, name)

            if value is not None and value < 0:
                raise ValueError(
                    f"{name} must not be negative."
                )

        if (
            self.max_cost is not None
            and self.max_cost < 0
        ):
            raise ValueError(
                "max_cost must not be negative."
            )

        currency = self.currency.strip().upper()

        if not currency:
            raise ValueError(
                "currency must not be empty."
            )

        object.__setattr__(
            self,
            "currency",
            currency,
        )


class LLMBudgetResolver:
    """Resolve LLM budget from ExecutionContext."""

    def resolve(
        self,
        context: ExecutionContext,
    ) -> LLMBudget:
        raw = context.budget.get(
            "llm",
            {},
        )

        if raw is None:
            raw = {}

        if not isinstance(raw, dict):
            raise ValueError(
                "budget['llm'] must be a mapping."
            )

        return LLMBudget(
            max_input_tokens=self._integer(
                raw.get("max_input_tokens"),
                "max_input_tokens",
            ),
            max_output_tokens=self._integer(
                raw.get("max_output_tokens"),
                "max_output_tokens",
            ),
            max_total_tokens=self._integer(
                raw.get("max_total_tokens"),
                "max_total_tokens",
            ),
            max_cost=self._number(
                raw.get("max_cost"),
                "max_cost",
            ),
            currency=self._currency(
                raw.get("currency", "USD")
            ),
        )

    @staticmethod
    def _integer(
        value: Any,
        field_name: str,
    ) -> int | None:
        if value is None:
            return None

        if (
            not isinstance(value, int)
            or isinstance(value, bool)
        ):
            raise ValueError(
                f"{field_name} must be an integer."
            )

        return value

    @staticmethod
    def _number(
        value: Any,
        field_name: str,
    ) -> float | None:
        if value is None:
            return None

        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
        ):
            raise ValueError(
                f"{field_name} must be a number."
            )

        return float(value)

    @staticmethod
    def _currency(value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError(
                "currency must be a string."
            )

        return value
