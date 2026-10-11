"""Tenant-scoped curriculum-to-learning competency graph.

An additive contract: no migration or change to existing Curriculum models.
This module does not infer an official syllabus or learner mastery.
"""
from __future__ import annotations

from dataclasses import dataclass


def _nonempty(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True, slots=True)
class CurriculumCompetencyLink:
    tenant_id: str
    curriculum_id: str
    concept_id: str
    competency_code: str
    prerequisites: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("tenant_id", "curriculum_id", "concept_id", "competency_code"):
            object.__setattr__(self, name, _nonempty(getattr(self, name), name))
        normalized = tuple(_nonempty(code, "prerequisite") for code in self.prerequisites)
        if len(normalized) != len(set(normalized)):
            raise ValueError("Duplicate prerequisites are forbidden")
        if self.competency_code in normalized:
            raise ValueError("A competency cannot require itself")
        object.__setattr__(self, "prerequisites", normalized)


class CurriculumCompetencyGraph:
    """Immutable, validated adjacency graph for a single tenant and curriculum."""

    def __init__(self, *, tenant_id: str, curriculum_id: str, links: tuple[CurriculumCompetencyLink, ...]):
        self.tenant_id = _nonempty(tenant_id, "tenant_id")
        self.curriculum_id = _nonempty(curriculum_id, "curriculum_id")
        self._links: dict[str, CurriculumCompetencyLink] = {}
        for link in links:
            if link.tenant_id != self.tenant_id or link.curriculum_id != self.curriculum_id:
                raise ValueError("Cross-tenant or cross-curriculum link rejected")
            if link.competency_code in self._links:
                raise ValueError("Duplicate competency code")
            self._links[link.competency_code] = link
        for code, link in self._links.items():
            for prerequisite in link.prerequisites:
                if prerequisite not in self._links:
                    raise ValueError(f"Unknown prerequisite for {code}: {prerequisite}")
        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(code: str) -> None:
            if code in visiting:
                raise ValueError("Circular competency prerequisites")
            if code in visited:
                return
            visiting.add(code)
            for dependency in self._links[code].prerequisites:
                visit(dependency)
            visiting.remove(code)
            visited.add(code)

        for code in self._links:
            visit(code)

    def competency(self, code: str) -> CurriculumCompetencyLink:
        return self._links[_nonempty(code, "competency_code")]

    def missing_prerequisites(self, code: str, mastered_codes: frozenset[str]) -> tuple[str, ...]:
        """Return direct missing prerequisites; mastery is supplied by the Learning Engine."""
        link = self.competency(code)
        return tuple(dep for dep in link.prerequisites if dep not in mastered_codes)

    def competencies_for_concept(self, concept_id: str) -> tuple[str, ...]:
        concept = _nonempty(concept_id, "concept_id")
        return tuple(code for code, link in self._links.items() if link.concept_id == concept)
