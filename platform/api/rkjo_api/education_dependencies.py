"""Education dependency providers."""

from uuid import UUID

from rkjo_api.dependencies import get_database_url, get_rag_answering_service
from rkjo_education.assessment.postgres_repository import PostgresAssessmentRepository
from rkjo_education.assessment.service import AssessmentService
from rkjo_education.learner.postgres_repository import PostgresLearnerRepository
from rkjo_education.learner.service import LearnerService
from rkjo_education.learning.postgres_repository import PostgresLearningRepository
from rkjo_education.learning.service import LearningService
from rkjo_education.tutor.service import TutorService
from rkjo_kernel.rag.retrieval_filters import RetrievalFilters


class TenantScopedRAGAnswerer:
    def answer(self, question: str, *, tenant_id: UUID):
        return get_rag_answering_service().answer(
            question,
            filters=RetrievalFilters(metadata={"tenant_id": str(tenant_id)}),
        )


def get_education_learner_service() -> LearnerService:
    return LearnerService(
        PostgresLearnerRepository(get_database_url())
    )


def get_education_learning_service() -> LearningService:
    return LearningService(
        PostgresLearningRepository(get_database_url())
    )


def get_education_assessment_service() -> AssessmentService:
    return AssessmentService(
        PostgresAssessmentRepository(get_database_url())
    )


def get_education_tutor_service() -> TutorService:
    database_url = get_database_url()
    return TutorService(
        learner_repository=PostgresLearnerRepository(database_url),
        learning_repository=PostgresLearningRepository(database_url),
        answerer=TenantScopedRAGAnswerer(),
    )
