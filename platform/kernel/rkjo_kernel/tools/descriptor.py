from typing import Any

from pydantic import BaseModel, Field, field_validator


class ToolDescriptor(BaseModel):
    """Metadata describing an executable RKJO tool."""

    name: str
    display_name: str
    description: str

    version: str = "1.0.0"

    input_schema: dict[str, Any] = Field(
        default_factory=dict
    )
    output_schema: dict[str, Any] = Field(
        default_factory=dict
    )

    tags: list[str] = Field(
        default_factory=list
    )

    timeout_ms: int = 30_000

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized_value = value.strip().lower()

        if not normalized_value:
            raise ValueError(
                "Tool name cannot be empty."
            )

        if " " in normalized_value:
            raise ValueError(
                "Tool name must not contain spaces."
            )

        return normalized_value

    @field_validator("timeout_ms")
    @classmethod
    def validate_timeout_ms(
        cls,
        value: int,
    ) -> int:
        if value < 0:
            raise ValueError(
                "timeout_ms cannot be negative."
            )

        return value
