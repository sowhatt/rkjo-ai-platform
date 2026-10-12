"""B+D grounded study views: source IDs, deterministic extraction, no fabricated knowledge."""
import pytest

from rkjo_education.curriculum.study_learning_views import build_study_views
from rkjo_education.curriculum.study_sources import StudyDocumentType, StudySegment, StudySourcePackage


def source():
    segments = (
        StudySegment.from_text(document_id="course-1", page=1, text=(
            "Cycle cardiaque\nLe ventricule droit propulse le sang vers les poumons. "
            "Le ventricule gauche propulse le sang vers les organes."
        )),
        StudySegment.from_text(document_id="course-1", page=3, text=(
            "Échanges pulmonaires\nLes échanges gazeux se produisent au niveau des alvéoles pulmonaires."
        )),
    )
    return StudySourcePackage(
        tenant_id="test-tenant", learner_id="test-student", programme_id="medicine",
        ue_id="physiologie", document_id="course-1", version=1,
        document_type=StudyDocumentType.CM, segments=segments,
    )


def test_notes_and_map_quote_only_existing_pages():
    document = source()
    views = build_study_views(document)
    assert views["generation_mode"] == "deterministic_excerpts"
    assert len(views["revision_notes"]) == 2
    assert views["mind_map"]["root"] == "physiologie"
    assert [note["citation"]["page"] for note in views["revision_notes"]] == [1, 3]
    original = {segment.segment_id: segment for segment in document.segments}
    for note in views["revision_notes"]:
        ref = note["citation"]["segment_id"]
        assert ref in original
        for excerpt in note["excerpts"]:
            assert excerpt in original[ref].text.replace("\n", " ") or excerpt in original[ref].text
    for branch in views["mind_map"]["branches"]:
        assert branch["id"] in original
        assert branch["page"] == original[branch["id"]].page


def test_page_cap_and_invalid_limit():
    assert len(build_study_views(source(), max_pages=1)["revision_notes"]) == 1
    for limit in (0, 51):
        with pytest.raises(ValueError):
            build_study_views(source(), max_pages=limit)


def test_existing_source_does_not_mutate():
    document = source()
    before = tuple(document.segments)
    build_study_views(document)
    assert document.segments == before
