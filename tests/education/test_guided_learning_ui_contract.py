"""Sprint 01 learning UI contract; does not replace interactive browser tests."""
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "apps/web/src"


def test_course_page_embeds_guided_learning_from_real_assessments():
    source = (WEB / "app/education/courses/[courseId]/page.tsx").read_text()
    assert 'import GuidedLearningActivity' in source
    assert 'questions={learningQuestions}' in source
    assert 'assessments.flatMap((item) => item.questions)' in source
    assert 'learningQuestions.length > 0' in source


def test_guided_learning_is_explicitly_ungraded():
    source = (WEB / "components/education/GuidedLearningActivity.tsx").read_text()
    assert "APPRENTISSAGE GUIDÉ · SANS NOTE" in source
    assert "aucune maîtrise ne sera enregistrée" in source
    assert "les réponses ne sont pas corrigées automatiquement" in source
    assert "évaluation autonome distincte" in source


def test_guided_learning_has_real_learner_interaction():
    source = (WEB / "components/education/GuidedLearningActivity.tsx").read_text()
    assert 'setStage("respond")' in source
    assert 'setStage("reflect")' in source
    assert "Ta réponse et ton raisonnement" in source
    assert "Question suivante" in source
    assert 'disabled={!reflection.trim()}' in source
