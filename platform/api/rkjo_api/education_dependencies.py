"""Education dependency providers."""

from uuid import UUID

from rkjo_api.dependencies import get_database_url, get_event_bus, get_rag_answering_service
from rkjo_education.assessment.postgres_repository import PostgresAssessmentRepository
from rkjo_education.course.postgres_repository import PostgresCourseRepository
from rkjo_education.assessment.service import AssessmentService
from rkjo_education.learner.postgres_repository import PostgresLearnerRepository
from rkjo_education.learner.service import LearnerService
from rkjo_education.learning.postgres_repository import PostgresLearningRepository
from rkjo_education.learning.service import LearningService
from rkjo_education.tutor.service import TutorService
from rkjo_kernel.rag.retrieval_filters import RetrievalFilters


class TenantScopedRAGAnswerer:
    def answer(
        self,
        question: str,
        *,
        tenant_id: UUID,
        document_ids: list[str],
    ):
        return get_rag_answering_service().answer(
            question,
            filters=RetrievalFilters(
                metadata={
                    "tenant_id": str(tenant_id),
                },
                document_ids=tuple(document_ids),
            ),
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
        course_repository=PostgresCourseRepository(database_url),
        answerer=TenantScopedRAGAnswerer(),
    )


def get_education_proof_service():
    from rkjo_education.intelligence.proof_application import (
        ProofApplicationService,
    )
    from rkjo_education.intelligence.proof_postgres_repository import (
        PostgresProofChallengeRepository,
    )

    database_url = get_database_url()

    return ProofApplicationService(
        assessment_repository=PostgresAssessmentRepository(database_url),
        proof_repository=PostgresProofChallengeRepository(database_url),
    )


def get_education_assessment_learning_service():
    from rkjo_education.intelligence.assessment_learning import (
        AssessmentLearningService,
    )
    from rkjo_education.intelligence.learning_evaluation import (
        LearningEvaluationService,
    )
    from rkjo_education.intelligence.proof_application import (
        ProofApplicationService,
    )
    from rkjo_education.intelligence.proof_postgres_repository import (
        PostgresProofChallengeRepository,
    )

    database_url = get_database_url()

    assessment_repository = PostgresAssessmentRepository(
        database_url
    )

    assessment_service = AssessmentService(
        assessment_repository
    )

    proof_service = ProofApplicationService(
        assessment_repository=assessment_repository,
        proof_repository=PostgresProofChallengeRepository(
            database_url
        ),
    )

    learning_evaluation_service = LearningEvaluationService(
        proof_service=proof_service,
    )

    return AssessmentLearningService(
        assessment_service=assessment_service,
        learning_evaluation_service=learning_evaluation_service,
    )


def get_education_event_publisher():
    from rkjo_education.events import EducationEventPublisher

    return EducationEventPublisher(get_event_bus())
