"""Tests for tenant-scoped curriculum competency graph."""
import pytest
from rkjo_education.curriculum.competency_graph import CurriculumCompetencyGraph, CurriculumCompetencyLink


def link(code, prereqs=(), tenant="school-a", curriculum="math-v1"):
    return CurriculumCompetencyLink(
        tenant_id=tenant, curriculum_id=curriculum,
        concept_id="equations", competency_code=code,
        prerequisites=prereqs,
    )


def graph(*links):
    return CurriculumCompetencyGraph(
        tenant_id="school-a", curriculum_id="math-v1", links=links,
    )


def test_math_prerequisite_and_concept_lookup():
    g = graph(link("MATH.CALCUL"), link("MATH.EQUATION", ("MATH.CALCUL",)))
    assert g.competencies_for_concept("equations") == ("MATH.CALCUL", "MATH.EQUATION")
    assert g.missing_prerequisites("MATH.EQUATION", frozenset()) == ("MATH.CALCUL",)
    assert g.missing_prerequisites("MATH.EQUATION", frozenset({"MATH.CALCUL"})) == ()


@pytest.mark.parametrize("prerequisites", [("A",), ("B", "B")])
def test_invalid_link_rejected(prerequisites):
    with pytest.raises(ValueError):
        link("A", prerequisites)


def test_cross_tenant_rejected():
    with pytest.raises(ValueError, match="Cross-tenant"):
        graph(link("A", tenant="school-b"))


def test_unknown_prerequisite_rejected():
    with pytest.raises(ValueError, match="Unknown prerequisite"):
        graph(link("A", ("MISSING",)))


def test_cycle_rejected():
    with pytest.raises(ValueError, match="Circular"):
        graph(link("A", ("B",)), link("B", ("A",)))


def test_duplicate_code_rejected():
    with pytest.raises(ValueError, match="Duplicate competency"):
        graph(link("A"), link("A"))
