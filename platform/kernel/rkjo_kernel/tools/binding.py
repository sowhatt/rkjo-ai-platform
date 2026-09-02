from pydantic import BaseModel, field_validator


class ToolBinding(BaseModel):
    """Bind one agent capability to one executable tool."""

    capability_name: str
    tool_name: str

    @field_validator(
        "capability_name",
        "tool_name",
    )
    @classmethod
    def normalize_name(
        cls,
        value: str,
    ) -> str:
        normalized_value = value.strip().lower()

        if not normalized_value:
            raise ValueError(
                "Binding name cannot be empty."
            )

        if " " in normalized_value:
            raise ValueError(
                "Binding names must not contain spaces."
            )

        return normalized_value
