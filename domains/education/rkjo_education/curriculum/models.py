"""Curriculum domain models."""

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
class CurriculumConcept:
    concept_id: str
    title: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "concept_id",
            _required(
                self.concept_id,
                field_name="concept_id",
            ),
        )
        object.__setattr__(
            self,
            "title",
            _required(
                self.title,
                field_name="title",
            ),
        )


@dataclass(frozen=True, slots=True)
class CurriculumTopic:
    topic_id: str
    title: str
    concepts: list[
        CurriculumConcept
    ] = field(
        default_factory=list
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "topic_id",
            _required(
                self.topic_id,
                field_name="topic_id",
            ),
        )
        object.__setattr__(
            self,
            "title",
            _required(
                self.title,
                field_name="title",
            ),
        )


@dataclass(frozen=True, slots=True)
class Curriculum:
    curriculum_id: str
    tenant_id: str
    country: str
    level: str
    subject: str
    academic_year: str
    topics: list[
        CurriculumTopic
    ] = field(
        default_factory=list
    )
    version: int = 1

    def __post_init__(self) -> None:
        for field_name in (
            "curriculum_id",
            "tenant_id",
            "country",
            "level",
            "subject",
            "academic_year",
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

        if self.version < 1:
            raise ValueError(
                "version must be >= 1."
            )

    @property
    def concept_count(self) -> int:
        return sum(
            len(topic.concepts)
            for topic in self.topics
        )
