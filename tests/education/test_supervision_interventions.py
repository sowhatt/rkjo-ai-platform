from uuid import uuid4

from rkjo_education.supervision.interventions import (
    TeacherIntervention,
    TeacherInterventionStore,
    TeacherInterventionType,
)


def test_teacher_interventions_are_tenant_and_learner_scoped():
    store = TeacherInterventionStore()
    tenant_id, other_tenant, learner_id = uuid4(), uuid4(), uuid4()
    created = store.create(TeacherIntervention(
        tenant_id=tenant_id,
        learner_id=learner_id,
        intervention_type=TeacherInterventionType.REQUEST_NEW_PROOF,
    ))
    assert created.status.value == "requested"
    assert store.list_for_learner(tenant_id=tenant_id, learner_id=learner_id) == [created]
    assert store.list_for_learner(tenant_id=other_tenant, learner_id=learner_id) == []


def test_teacher_intervention_copy_cannot_mutate_store():
    store = TeacherInterventionStore()
    intervention = TeacherIntervention(
        tenant_id=uuid4(), learner_id=uuid4(),
        intervention_type=TeacherInterventionType.ASSIGN_CONSOLIDATION,
    )
    created = store.create(intervention)
    created.message = "changed outside store"
    saved = store.list_for_learner(tenant_id=intervention.tenant_id, learner_id=intervention.learner_id)[0]
    assert saved.message is None
