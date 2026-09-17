from __future__ import annotations

from typing import Protocol
from uuid import UUID

from rkjo_education.learner.repository import LearnerRepository
from rkjo_education.learning.repository import LearningRepository

from .models import TutorAnswer, TutorSource


class GroundedTutorAnswer(Protocol):
    answer: str
    sanitized_query: str
    sources: list


class TutorAnswerer(Protocol):
    def answer(self, question: str, *, tenant_id: UUID) -> GroundedTutorAnswer: ...


class TutorService:
    def __init__(
        self,
        *,
        learner_repository: LearnerRepository,
        learning_repository: LearningRepository,
        answerer: TutorAnswerer,
        weak_competency_threshold: int = 70,
    ) -> None:
        self._learner_repository = learner_repository
        self._learning_repository = learning_repository
        self._answerer = answerer
        self._weak_competency_threshold = weak_competency_threshold

    def ask(
        self,
        *,
        tenant_id: UUID,
        learner_id: UUID,
        course_id: UUID,
        question: str,
    ) -> TutorAnswer:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question is required")

        learner = self._learner_repository.get(
            tenant_id=tenant_id,
            learner_id=learner_id,
        )
        if learner is None:
            raise LookupError("learner not found")

        progress = self._learning_repository.find_progress(
            tenant_id=tenant_id,
            learner_id=learner_id,
            course_id=course_id,
        )
        completion_percent = progress.completion_percent if progress else 0
        competency_scores = progress.competency_scores if progress else {}
        weak_competencies = sorted(
            code
            for code, score in competency_scores.items()
            if score < self._weak_competency_threshold
        )

        weakness_instruction = (
            ", ".join(weak_competencies)
            if weak_competencies
            else "aucune faiblesse identifiée"
        )
        adapted_question = (
            f"Tu es un tuteur pédagogique. Réponds à un élève de niveau {learner.level}. "
            f"Le cours est complété à {completion_percent}%. "
            f"Compétences à renforcer: {weakness_instruction}. "
            "Explique simplement, étape par étape, sans donner plus d'informations que nécessaire, "
            "et termine par une courte question de vérification. "
            f"Question de l'élève: {normalized_question}"
        )

        grounded = self._answerer.answer(adapted_question, tenant_id=tenant_id)

        return TutorAnswer(
            learner_id=learner_id,
            course_id=course_id,
            answer=grounded.answer,
            adapted_question=adapted_question,
            level=learner.level,
            completion_percent=completion_percent,
            weak_competencies=weak_competencies,
            sources=[
                TutorSource(
                    citation=source.citation,
                    document_id=source.document_id,
                    chunk_id=source.chunk_id,
                    score=source.score,
                )
                for source in grounded.sources
            ],
        )
