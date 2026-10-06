from rkjo_education.alignment import ReferentialCompetency
from rkjo_education.ingestion.aligned_copy import CorrectedCopyAlignmentService


def test_corrected_copy_flows_to_mastery_evidence_question_by_question():
    referential = [
        ReferentialCompetency(
            code="MED.BIO.CELL",
            label="Biologie cellulaire",
            keywords=("cellule", "membrane"),
            importance=3,
        )
    ]
    rows = CorrectedCopyAlignmentService().process(
        text=(
            "Question 1: cellule et membrane. 2/2\n"
            "Question 2: membrane. 0/2"
        ),
        referential=referential,
    )
    assert len(rows) == 2
    assert rows[0].competency_code == "MED.BIO.CELL"
    assert rows[0].requires_confirmation is False
    assert rows[0].evidence.to_mastery_observation().score == 1.0
    assert rows[1].requires_confirmation is True
    assert rows[1].evidence.to_mastery_observation() is None
    assert rows[1].evidence.to_mastery_observation(confirmed=True).score == 0.0


def test_unaligned_question_never_creates_learning_evidence():
    rows = CorrectedCopyAlignmentService().process(
        text="Question 1: contenu inconnu. 1/2",
        referential=[
            ReferentialCompetency(code="MED.BIO.CELL", label="Cellule", keywords=("cellule",))
        ],
    )
    assert rows[0].competency_code is None
    assert rows[0].evidence is None
    assert rows[0].requires_confirmation is True
