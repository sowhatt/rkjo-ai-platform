"""Education dependency providers."""

from rkjo_api.dependencies import get_database_url
from rkjo_education.assessment.postgres_repository import PostgresAssessmentRepository
from rkjo_education.assessment.service import AssessmentService
from rkjo_education.learner.postgres_repository import PostgresLearnerRepository
from rkjo_education.learner.service import LearnerService
from rkjo_education.learning.postgres_repository import PostgresLearningRepository
from rkjo_education.learning.service import LearningService


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
