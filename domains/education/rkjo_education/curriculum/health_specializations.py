"""Educational health-track catalog (illustrative, NOT official curricula).

Official national/university syllabi must be imported, referenced and approved
before these topics can be presented as accredited programme requirements.
No patient-specific diagnosis, prescribing or treatment decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from rkjo_education.curriculum.competency_graph import (
    CurriculumCompetencyGraph,
    CurriculumCompetencyLink,
)


class HealthTrack(StrEnum):
    MEDICINE = "medicine"
    PHARMACY = "pharmacy"
    NURSING = "nursing"


@dataclass(frozen=True, slots=True)
class HealthEducationProfile:
    track: HealthTrack
    label: str
    model_profile: str
    learning_modes: tuple[str, ...]
    requires_verified_sources: bool = True
    requires_human_review_for_clinical_assessment: bool = True
    patient_specific_advice_allowed: bool = False


HEALTH_EDUCATION_PROFILES: dict[HealthTrack, HealthEducationProfile] = {
    HealthTrack.MEDICINE: HealthEducationProfile(
        HealthTrack.MEDICINE,
        "Médecine",
        "rkjo_medical_tutor",
        ("cours", "qcm", "anatomie", "cas_clinique_simule", "oral"),
    ),
    HealthTrack.PHARMACY: HealthEducationProfile(
        HealthTrack.PHARMACY,
        "Pharmacie",
        "rkjo_pharmacy_tutor",
        ("cours", "qcm", "pharmacologie", "calculs_de_doses_simules", "oral"),
    ),
    HealthTrack.NURSING: HealthEducationProfile(
        HealthTrack.NURSING,
        "Soins infirmiers",
        "rkjo_nursing_tutor",
        ("cours", "qcm", "simulation_soins", "raisonnement_clinique_simule", "oral"),
    ),
}


# Demonstration data only: not a French, Beninese or university-approved syllabus.
_DEMO_COMPETENCIES: dict[HealthTrack, tuple[tuple[str, str, tuple[str, ...]], ...]] = {
    HealthTrack.MEDICINE: (
        ("MED.ANATOMY", "anatomie", ()),
        ("MED.PHYSIOLOGY", "physiologie", ("MED.ANATOMY",)),
        ("MED.SIM_CASE", "cas_simule", ("MED.PHYSIOLOGY",)),
    ),
    HealthTrack.PHARMACY: (
        ("PHA.CHEMISTRY", "chimie", ()),
        ("PHA.PHARMACOLOGY", "pharmacologie", ("PHA.CHEMISTRY",)),
        ("PHA.SIM_SAFETY", "securite_simulee", ("PHA.PHARMACOLOGY",)),
    ),
    HealthTrack.NURSING: (
        ("NUR.ANATOMY", "anatomie", ()),
        ("NUR.FUNDAMENTALS", "fondamentaux_soins", ("NUR.ANATOMY",)),
        ("NUR.SIM_CARE", "simulation_soins", ("NUR.FUNDAMENTALS",)),
    ),
}


def health_profile(track: HealthTrack | str) -> HealthEducationProfile:
    return HEALTH_EDUCATION_PROFILES[HealthTrack(track)]


def demonstration_health_graph(
    *, tenant_id: str, curriculum_id: str, track: HealthTrack | str
) -> CurriculumCompetencyGraph:
    """Build an isolated example graph; callers must not label it official."""
    selected = HealthTrack(track)
    links = tuple(
        CurriculumCompetencyLink(
            tenant_id=tenant_id,
            curriculum_id=curriculum_id,
            concept_id=concept,
            competency_code=code,
            prerequisites=prerequisites,
        )
        for code, concept, prerequisites in _DEMO_COMPETENCIES[selected]
    )
    return CurriculumCompetencyGraph(
        tenant_id=tenant_id, curriculum_id=curriculum_id, links=links
    )
