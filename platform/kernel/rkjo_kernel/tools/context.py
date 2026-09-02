from typing import Any

from pydantic import BaseModel, Field, field_validator


class ToolExecutionContext(BaseModel):
    """Execution context propagated to RKJO tools."""

    tenant_id: str
    agent_name: str
    capability_name: str

    workflow_execution_id: str | None = None
    workflow_step_id: str | None = None
    correlation_id: str | None = None

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    @field_validator(
        "tenant_id",
        "agent_name",
        "capability_name",
    )
    @classmethod
    def normalize_identifier(
        cls,
        value: str,
    ) -> str:
        normalized_value = value.strip().lower()

        if not normalized_value:
            raise ValueError(
                "Execution context identifiers "
                "cannot be empty."
            )

        if " " in normalized_value:
            raise ValueError(
                "Execution context identifiers "
                "must not contain spaces."
            )

        return normalized_value
