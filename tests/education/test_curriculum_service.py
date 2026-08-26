import pytest

from rkjo_education.curriculum.models import (
    Curriculum,
    CurriculumConcept,
    CurriculumTopic,
)
from rkjo_education.curriculum.repository import (
    InMemoryCurriculumRepository,
)
from rkjo_education.curriculum.service import (
    CurriculumService,
)


def build_curriculum(
    tenant_id: str = "demo-tenant",
) -> Curriculum:
    return Curriculum(
        curriculum_id="fr-terminale-svt-2026",
        tenant_id=tenant_id,
        country="FR",
        level="Terminale",
        subject="SVT",
        academic_year="2026-2027",
        topics=[
            CurriculumTopic(
                topic_id="genetique",
                title="Génétique et évolution",
                concepts=[
                    CurriculumConcept(
                        concept_id="adn",
                        title="ADN",
                    ),
                    CurriculumConcept(
                        concept_id="mutation",
                        title="Mutation",
                    ),
                ],
            ),
        ],
    )


def test_create_and_get_curriculum():
    repository = InMemoryCurriculumRepository()
    service = CurriculumService(repository)

    curriculum = build_curriculum()

    created = service.create(curriculum)

    assert created.curriculum_id == (
        "fr-terminale-svt-2026"
    )
    assert created.tenant_id == "demo-tenant"
    assert created.concept_count == 2
    assert created.version == 1

    loaded = service.get(
        tenant_id="demo-tenant",
        curriculum_id="fr-terminale-svt-2026",
    )

    assert loaded == created


def test_curriculum_is_tenant_safe():
    repository = InMemoryCurriculumRepository()
    service = CurriculumService(repository)

    service.create(build_curriculum())

    with pytest.raises(LookupError):
        service.get(
            tenant_id="other-tenant",
            curriculum_id="fr-terminale-svt-2026",
        )
