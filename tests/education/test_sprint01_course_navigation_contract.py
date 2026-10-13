"""Static regression checks for Sprint 01: truthful course navigation.

These do not replace browser/API E2E tests.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "apps/web/src"


def test_course_catalog_loads_from_existing_api():
    source = (WEB / "app/education/courses/page.tsx").read_text(encoding="utf-8")
    assert 'fetch("/api/education/courses"' in source
    assert 'courses.map(' in source
    assert 'Aucun cours disponible' in source
    assert '64%' not in source
    assert 'href="/education/session"' not in source


def test_course_detail_reads_course_and_assessments():
    source = (WEB / "app/education/courses/[courseId]/page.tsx").read_text(encoding="utf-8")
    assert "/api/education/courses/${id}" in source
    assert "/assessments" in source
    assert "Aucune évaluation" in source
    assert "session individuelle" in source


def test_home_does_not_start_session_without_course():
    source = (WEB / "components/education/EducationHome.tsx").read_text(encoding="utf-8")
    assert 'href="/education/courses" className="rkjo-start"' in source
    assert "Indicateurs ci-dessous : démonstration" in source
