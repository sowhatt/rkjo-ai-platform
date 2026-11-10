from typing import Any

from pydantic import BaseModel, Field, field_validator


class ToolExecutionContext(BaseModel):
    """Execution context propagated to RKJO tools."""

    tenant_id: str
    agent_name: str
    capability_name: str

    mission_id: str | None = None
    trace_id: str | None = None
    workflow_execution_id: str | None = None
    workflow_step_id: str | None = None
    correlation_id: str | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tenant_id", "agent_name", "capability_name")
    @classmethod
    def normalize_routing_identifier(cls, value: str) -> str:
        normalized_value = value.strip().lower()
        if not normalized_value:
            raise ValueError("Execution context identifiers cannot be empty.")
        if " " in normalized_value:
            raise ValueError(
                "Execution context identifiers must not contain spaces."
            )
        return normalized_value

    @field_validator(
        "mission_id",
        "trace_id",
        "workflow_execution_id",
        "workflow_step_id",
        "correlation_id",
    )
    @classmethod
    def preserve_execution_identity(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Execution identity cannot be empty.")
        return normalized_value
