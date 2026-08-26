"""Course domain models."""

from __future__ import annotations

from dataclasses import dataclass, field


def _required(
    value: str,
    *,
    field_name: str,
) -> str:
    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} must not be empty."
        )

    return normalized


@dataclass(frozen=True, slots=True)
class Course:
    course_id: str
    tenant_id: str
    title: str
    subject: str
    level: str
    curriculum_id: str | None = None
    document_ids: list[str] = field(
        default_factory=list
    )

    def __post_init__(self) -> None:
        for field_name in (
            "course_id",
            "tenant_id",
            "title",
            "subject",
            "level",
        ):
            object.__setattr__(
                self,
                field_name,
                _required(
                    getattr(
                        self,
                        field_name,
                    ),
                    field_name=field_name,
                ),
            )

        if self.curriculum_id is not None:
            object.__setattr__(
                self,
                "curriculum_id",
                _required(
                    self.curriculum_id,
                    field_name=(
                        "curriculum_id"
                    ),
                ),
            )

        normalized_documents: list[
            str
        ] = []

        seen: set[str] = set()

        for document_id in self.document_ids:
            normalized = _required(
                document_id,
                field_name="document_id",
            )

            if normalized in seen:
                continue

            seen.add(normalized)
            normalized_documents.append(
                normalized
            )

        object.__setattr__(
            self,
            "document_ids",
            normalized_documents,
        )
