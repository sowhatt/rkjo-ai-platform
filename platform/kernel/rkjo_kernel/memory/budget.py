from __future__ import annotations

from dataclasses import dataclass

from .models import MemoryItem


@dataclass(frozen=True, slots=True)
class ContextBudget:
    max_items: int | None = None
    max_characters: int | None = None

    def __post_init__(self) -> None:
        if self.max_items is not None and self.max_items <= 0:
            raise ValueError("max_items must be greater than zero")
        if self.max_characters is not None and self.max_characters <= 0:
            raise ValueError("max_characters must be greater than zero")


class ContextBudgetEnforcer:
    """Apply deterministic limits while preserving selection order."""

    def apply(
        self,
        items: tuple[MemoryItem, ...],
        *,
        budget: ContextBudget,
    ) -> tuple[MemoryItem, ...]:
        selected: list[MemoryItem] = []
        used_characters = 0

        for item in items:
            if budget.max_items is not None and len(selected) >= budget.max_items:
                break

            item_characters = len(item.content)
            if (
                budget.max_characters is not None
                and used_characters + item_characters > budget.max_characters
            ):
                continue

            selected.append(item)
            used_characters += item_characters

        return tuple(selected)
