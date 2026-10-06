from rkjo_education.ingestion.corrected_copy import CorrectedCopySplitter


def test_splits_corrected_copy_question_by_question_and_keeps_marks():
    blocks = CorrectedCopySplitter().split(
        "Question 1: Définir la cellule. Note: 2/2\n"
        "Question 2: Expliquer la mitochondrie. 1,5/3"
    )
    assert [item.question_ref for item in blocks] == ["q1", "q2"]
    assert blocks[0].earned_points == 2
    assert blocks[0].max_points == 2
    assert blocks[1].earned_points == 1.5
    assert blocks[1].max_points == 3


def test_missing_score_is_not_invented():
    block = CorrectedCopySplitter().split("Q3: Justifier la réponse.")[0]
    assert block.question_ref == "q3"
    assert block.earned_points is None
    assert block.max_points is None


def test_unstructured_copy_is_preserved_as_single_block():
    blocks = CorrectedCopySplitter().split("Copie corrigée sans numérotation explicite")
    assert len(blocks) == 1
    assert blocks[0].question_ref == "document"
