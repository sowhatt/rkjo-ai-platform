"""Sprint 01 learning UI contract; does not replace interactive browser tests."""
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "apps/web/src"


def test_course_page_embeds_guided_learning_from_real_assessments():
    source = (WEB / "app/education/courses/[courseId]/page.tsx").read_text()
    assert 'import GuidedLearningActivity' in source
    assert 'questions={learningQuestions}' in source
    assert 'assessments.flatMap((item) => item.questions.map((question) => ({ ...question, assessment_id: item.id })))' in source
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


def test_guided_feedback_preserves_question_ownership_and_fails_closed():
    page = (WEB / "app/education/courses/[courseId]/page.tsx").read_text()
    component = (WEB / "components/education/GuidedLearningActivity.tsx").read_text()
    gateway = (WEB / "app/api/education/tutor/feedback/route.ts").read_text()
    assert "assessment_id: item.id" in page
    assert "courseId={course.course_id}" in page
    for field in ("course_id: courseId", "assessment_id: active.assessment_id",
                  "question_id: active.id", "student_answer: response.trim()"):
        assert field in component
    assert 'fetch("/api/education/tutor/feedback"' in component
    assert "role=\"alert\"" in component
    assert "readPilotSession(request)" in gateway
    assert "status: 401" in gateway
    assert "status: 403" in gateway
    assert "RKJO_OPERATOR_API_KEY" not in gateway
    assert "backendPilotBearer" not in gateway


def test_local_individual_student_demo_never_uses_shared_identity():
    component = (WEB / "components/education/GuidedLearningActivity.tsx").read_text()
    session = (WEB / "app/api/education/student/session/route.ts").read_text()
    auth = (WEB / "lib/education/individualStudentSession.ts").read_text()
    feedback = (WEB / "app/api/education/tutor/feedback/route.ts").read_text()
    assert 'fetch("/api/education/student/session"' in component
    assert "disabled={feedbackBusy || !studentConnected}" in component
    assert "studentDemoAllowed(request)" in session
    assert "httpOnly: true" in auth
    assert 'process.env.NODE_ENV === "development"' in auth
    assert "RKJO_EDUCATION_STUDENT_ID" in auth
    assert "getStudentSession(request)" in feedback
    assert "studentBackendBearer(identity)" in feedback
    assert "readPilotSession(request)" in feedback
    assert '"RKJO_OPERATOR_API_KEY"' not in feedback
    assert "backendPilotBearer" not in feedback
