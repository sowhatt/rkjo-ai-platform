from dataclasses import dataclass
from uuid import uuid4

from rkjo_education.learner.repository import InMemoryLearnerRepository
from rkjo_education.learner.service import LearnerService
from rkjo_education.learning.repository import InMemoryLearningRepository
from rkjo_education.learning.service import LearningService
from rkjo_education.tutor.service import TutorService


@dataclass
class Source:
    citation: int = 1
    document_id: str = "doc-1"
    chunk_id: str = "chunk-1"
    score: float = 0.9


@dataclass
class Answer:
    answer: str = "Une fraction représente une partie d'un tout."
    sanitized_query: str = "question"
    sources: list = None

    def __post_init__(self):
        if self.sources is None:
            self.sources = [Source()]


class FakeAnswerer:
    def __init__(self):
        self.question = None
        self.tenant_id = None

    def answer(self, question: str, *, tenant_id):
        self.question = question
        self.tenant_id = tenant_id
        return Answer()


def test_tutor_adapts_rag_prompt_to_learner_progress():
    tenant_id = uuid4()
    learner_repo = InMemoryLearnerRepository()
    learning_repo = InMemoryLearningRepository()
    learner = LearnerService(learner_repo).create(
        tenant_id=tenant_id,
        first_name="Awa",
        last_name="Mensah",
        level="CE2",
    )
    course_id = uuid4()
    LearningService(learning_repo).record_progress(
        tenant_id=tenant_id,
        learner_id=learner.id,
        course_id=course_id,
        completion_percent=45,
        competency_scores={"MATH.FRACTION": 50, "MATH.ADD": 90},
    )
    answerer = FakeAnswerer()
    tutor = TutorService(
        learner_repository=learner_repo,
        learning_repository=learning_repo,
        answerer=answerer,
    )

    result = tutor.ask(
        tenant_id=tenant_id,
        learner_id=learner.id,
        course_id=course_id,
        question="C'est quoi une fraction ?",
    )

    assert result.level == "CE2"
    assert result.completion_percent == 45
    assert result.weak_competencies == ["MATH.FRACTION"]
    assert "niveau CE2" in result.adapted_question
    assert "45%" in result.adapted_question
    assert "MATH.FRACTION" in result.adapted_question
    assert answerer.tenant_id == tenant_id
    assert result.sources[0].document_id == "doc-1"
