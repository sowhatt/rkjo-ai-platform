from __future__ import annotations

from dataclasses import dataclass
import re

from .models import MemoryItem, MemoryScope


_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class ContextSelectionPolicy:
    """Deterministic V1 policy for selecting relevant memory."""

    max_items: int = 20
    min_importance: float = 0.0
    mission_scope_boost: float = 0.15
    entity_scope_boost: float = 0.05
    relevance_weight: float = 0.60
    importance_weight: float = 0.40

    def __post_init__(self) -> None:
        if self.max_items <= 0:
            raise ValueError("max_items must be greater than zero")
        if not 0.0 <= self.min_importance <= 1.0:
            raise ValueError("min_importance must be between 0.0 and 1.0")
        for field_name in (
            "mission_scope_boost",
            "entity_scope_boost",
            "relevance_weight",
            "importance_weight",
        ):
            if getattr(self, field_name) < 0.0:
                raise ValueError(f"{field_name} must not be negative")


class ContextSelector:
    """Rank memory without provider, vector-store or LLM dependencies."""

    def select(
        self,
        items: tuple[MemoryItem, ...],
        *,
        query: str | None = None,
        policy: ContextSelectionPolicy | None = None,
    ) -> tuple[MemoryItem, ...]:
        active_policy = policy or ContextSelectionPolicy()
        query_tokens = self._tokens(query)

        candidates = [
            item
            for item in items
            if item.importance >= active_policy.min_importance
        ]

        ranked = sorted(
            candidates,
            key=lambda item: self._rank_key(
                item,
                query_tokens=query_tokens,
                policy=active_policy,
            ),
            reverse=True,
        )

        return tuple(ranked[: active_policy.max_items])

    def _rank_key(
        self,
        item: MemoryItem,
        *,
        query_tokens: set[str],
        policy: ContextSelectionPolicy,
    ) -> tuple[float, float, object, str]:
        relevance = self._relevance(item, query_tokens)
        scope_boost = 0.0
        if item.scope is MemoryScope.MISSION:
            scope_boost = policy.mission_scope_boost
        elif item.scope is MemoryScope.ENTITY:
            scope_boost = policy.entity_scope_boost

        score = (
            relevance * policy.relevance_weight
            + item.importance * policy.importance_weight
            + scope_boost
        )
        return (score, item.importance, item.created_at, item.memory_id)

    @classmethod
    def _relevance(
        cls,
        item: MemoryItem,
        query_tokens: set[str],
    ) -> float:
        if not query_tokens:
            return 0.0
        content_tokens = cls._tokens(item.content)
        if not content_tokens:
            return 0.0
        overlap = len(query_tokens & content_tokens)
        return overlap / len(query_tokens)

    @staticmethod
    def _tokens(value: str | None) -> set[str]:
        if value is None:
            return set()
        return {
            token.casefold()
            for token in _TOKEN_RE.findall(value)
            if token.strip()
        }
