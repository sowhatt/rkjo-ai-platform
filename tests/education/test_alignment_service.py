from uuid import uuid4

from rkjo_education.alignment import EducationAlignmentService, ReferentialCompetency


def _referential():
    return [
        ReferentialCompetency(
            code="MED.BIO.CELL",
            label="Biologie cellulaire",
            keywords=("cellule", "membrane", "mitochondrie"),
            importance=3,
        ),
        ReferentialCompetency(
            code="MED.BIO.GEN",
            label="Génétique",
            keywords=("adn", "gène", "chromosome"),
            importance=3,
        ),
    ]


def test_high_confidence_alignment_is_directly_usable():
    decision = EducationAlignmentService().align(
        source_id=uuid4(),
        text="La cellule possède une membrane et une mitochondrie.",
        referential=_referential(),
    )
    assert decision.candidate.competency_code == "MED.BIO.CELL"
    assert decision.requires_learner_confirmation is False


def test_low_confidence_alignment_requires_student_confirmation():
    service = EducationAlignmentService()
    decision = service.align(
        source_id=uuid4(),
        text="La membrane plasmique.",
        referential=_referential(),
    )
    assert decision.candidate.competency_code == "MED.BIO.CELL"
    assert decision.requires_learner_confirmation is True
    corrected = service.confirm(decision, competency_code="MED.BIO.GEN")
    assert corrected.candidate.competency_code == "MED.BIO.GEN"
    assert corrected.candidate.reason == "learner_confirmed"
    assert corrected.requires_learner_confirmation is False


def test_unknown_content_is_never_silently_aligned():
    decision = EducationAlignmentService().align(
        source_id=uuid4(),
        text="contenu sans correspondance",
        referential=_referential(),
    )
    assert decision.candidate is None
    assert decision.requires_learner_confirmation is True
