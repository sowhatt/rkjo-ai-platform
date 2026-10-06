from uuid import uuid4

from rkjo_education.alignment import ReferentialCompetency
from rkjo_education.alignment.pipeline import EducationAlignmentPipeline, SourceSegment


def test_pipeline_keeps_alignment_per_source_segment():
    referential = [
        ReferentialCompetency(code="BIO.CELL", label="Cellule", keywords=("cellule", "membrane")),
        ReferentialCompetency(code="BIO.GEN", label="Génétique", keywords=("adn", "chromosome")),
    ]
    results = EducationAlignmentPipeline().align_segments(
        [
            SourceSegment(uuid4(), "q1", "cellule et membrane"),
            SourceSegment(uuid4(), "q2", "adn"),
        ],
        referential,
    )
    assert results[0].decision.candidate.competency_code == "BIO.CELL"
    assert results[0].decision.requires_learner_confirmation is False
    assert results[1].decision.candidate.competency_code == "BIO.GEN"
    assert results[1].decision.requires_learner_confirmation is True
    assert EducationAlignmentPipeline.accepted_competencies(results) == {"BIO.CELL"}
