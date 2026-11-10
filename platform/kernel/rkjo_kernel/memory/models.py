from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class MemoryScope(str, Enum):
    """Scope controlling where a memory can be retrieved."""

    EXECUTION = "execution"
    MISSION = "mission"
    USER = "user"
    TENANT = "tenant"
    DOMAIN = "domain"
    ENTITY = "entity"


class MemoryType(str, Enum):
    """Semantic type of a memory item."""

    FACT = "fact"
    OBSERVATION = "observation"
    PREFERENCE = "preference"
    DECISION = "decision"
    SUMMARY = "summary"
    EVENT = "event"


@dataclass(frozen=True, slots=True)
class MemoryItem:
    """Provider-neutral unit of durable or working memory."""

    content: str
    tenant_id: str
    scope: MemoryScope
    memory_type: MemoryType = MemoryType.FACT

    memory_id: str = field(default_factory=lambda: str(uuid4()))

    mission_id: str | None = None
    execution_id: str | None = None
    user_id: str | None = None
    domain: str | None = None
    entity_id: str | None = None

    importance: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("Memory content must not be empty")

        if not self.tenant_id.strip():
            raise ValueError("tenant_id must not be empty")

        if not 0.0 <= self.importance <= 1.0:
            raise ValueError("importance must be between 0.0 and 1.0")

        required_scope_fields = {
            MemoryScope.EXECUTION: ("execution_id", self.execution_id),
            MemoryScope.MISSION: ("mission_id", self.mission_id),
            MemoryScope.USER: ("user_id", self.user_id),
            MemoryScope.DOMAIN: ("domain", self.domain),
            MemoryScope.ENTITY: ("entity_id", self.entity_id),
        }

        requirement = required_scope_fields.get(self.scope)
        if requirement is not None:
            field_name, value = requirement
            if value is None or not value.strip():
                raise ValueError(
                    f"{field_name} is required for {self.scope.value} scope"
                )


@dataclass(frozen=True, slots=True)
class MemoryQuery:
    """Storage-neutral query used to retrieve memory."""

    tenant_id: str

    scopes: tuple[MemoryScope, ...] = ()
    memory_types: tuple[MemoryType, ...] = ()

    mission_id: str | None = None
    execution_id: str | None = None
    user_id: str | None = None
    domain: str | None = None
    entity_id: str | None = None

    text: str | None = None
    min_importance: float | None = None
    limit: int = 20

    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("tenant_id must not be empty")

        if self.limit <= 0:
            raise ValueError("limit must be greater than zero")

        if (
            self.min_importance is not None
            and not 0.0 <= self.min_importance <= 1.0
        ):
            raise ValueError(
                "min_importance must be between 0.0 and 1.0"
            )
