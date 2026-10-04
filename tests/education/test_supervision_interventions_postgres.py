import os
from uuid import uuid4

import pytest

from rkjo_education.supervision.interventions import (
    PostgresTeacherInterventionStore,
    TeacherIntervention,
    TeacherInterventionType,
)


DATABASE_URL = os.getenv("RKJO_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="RKJO_DATABASE_URL is not configured",
)


def test_interventions_are_durable_ordered_and_tenant_scoped():
    store = PostgresTeacherInterventionStore(DATABASE_URL)
    store.initialize_schema()

    tenant_id = uuid4()
    other_tenant = uuid4()
    learner_id = uuid4()

    first = store.create(TeacherIntervention(
        tenant_id=tenant_id,
        learner_id=learner_id,
        intervention_type=TeacherInterventionType.REQUEST_NEW_PROOF,
    ))
    second = store.create(TeacherIntervention(
        tenant_id=tenant_id,
        learner_id=learner_id,
        intervention_type=TeacherInterventionType.SEND_MESSAGE,
        message="Reprends calmement l'exercice puis explique ton raisonnement.",
    ))
    store.create(TeacherIntervention(
        tenant_id=other_tenant,
        learner_id=learner_id,
        intervention_type=TeacherInterventionType.ASSIGN_CONSOLIDATION,
    ))

    restarted_store = PostgresTeacherInterventionStore(DATABASE_URL)
    restarted_store.initialize_schema()

    assert restarted_store.list_for_learner(
        tenant_id=tenant_id,
        learner_id=learner_id,
    ) == [first, second]
    assert restarted_store.list_for_learner(
        tenant_id=uuid4(),
        learner_id=learner_id,
    ) == []


def test_intervention_insert_is_idempotent():
    store = PostgresTeacherInterventionStore(DATABASE_URL)
    store.initialize_schema()
    intervention = TeacherIntervention(
        tenant_id=uuid4(),
        learner_id=uuid4(),
        intervention_type=TeacherInterventionType.ASSIGN_CONSOLIDATION,
    )

    store.create(intervention)
    store.create(intervention)

    assert store.list_for_learner(
        tenant_id=intervention.tenant_id,
        learner_id=intervention.learner_id,
    ) == [intervention]


def test_intervention_delivery_and_acknowledgement_lifecycle():
    store = PostgresTeacherInterventionStore(DATABASE_URL)
    store.initialize_schema()
    tenant_id, learner_id = uuid4(), uuid4()
    created = store.create(TeacherIntervention(
        tenant_id=tenant_id,
        learner_id=learner_id,
        intervention_type=TeacherInterventionType.SEND_MESSAGE,
        message="Je suis ton travail.",
    ))

    delivered = store.mark_delivered(tenant_id=tenant_id, learner_id=learner_id)
    current = next(item for item in delivered if item.intervention_id == created.intervention_id)
    assert current.status.value == "delivered"
    assert current.delivered_at is not None
    assert current.acknowledged_at is None

    acknowledged = store.acknowledge(
        tenant_id=tenant_id,
        learner_id=learner_id,
        intervention_id=created.intervention_id,
    )
    assert acknowledged is not None
    assert acknowledged.status.value == "acknowledged"
    assert acknowledged.delivered_at is not None
    assert acknowledged.acknowledged_at is not None

    restarted = PostgresTeacherInterventionStore(DATABASE_URL)
    saved = restarted.list_for_learner(tenant_id=tenant_id, learner_id=learner_id)
    current = next(item for item in saved if item.intervention_id == created.intervention_id)
    assert current.status.value == "acknowledged"


def test_exact_consolidation_target_survives_restart():
    store = PostgresTeacherInterventionStore(DATABASE_URL)
    store.initialize_schema()
    tenant_id, learner_id = uuid4(), uuid4()
    assessment_id, question_id = uuid4(), uuid4()
    created = store.create(TeacherIntervention(
        tenant_id=tenant_id,
        learner_id=learner_id,
        intervention_type=TeacherInterventionType.ASSIGN_CONSOLIDATION,
        message=str(assessment_id),
        target_assessment_id=assessment_id,
        target_question_id=question_id,
        competency_code="MATH.ADD",
    ))

    restarted = PostgresTeacherInterventionStore(DATABASE_URL)
    saved = restarted.list_for_learner(
        tenant_id=tenant_id,
        learner_id=learner_id,
    )[0]

    assert saved == created
    assert saved.target_assessment_id == assessment_id
    assert saved.target_question_id == question_id
    assert saved.competency_code == "MATH.ADD"
