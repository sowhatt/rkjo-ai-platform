"""Contracts for three educational health tracks, not clinical decision support."""
import pytest

from rkjo_education.curriculum.health_specializations import (
    HealthTrack, health_profile, demonstration_health_graph,
)


@pytest.mark.parametrize("track", list(HealthTrack))
def test_profile_is_strictly_educational(track):
    profile = health_profile(track)
    assert profile.model_profile.startswith("rkjo_")
    assert profile.requires_verified_sources
    assert profile.requires_human_review_for_clinical_assessment
    assert not profile.patient_specific_advice_allowed
    assert len(profile.learning_modes) >= 3


@pytest.mark.parametrize("track", list(HealthTrack))
def test_demo_curriculum_has_valid_prerequisite_chain(track):
    graph = demonstration_health_graph(
        tenant_id="university-1", curriculum_id="demo-2026", track=track,
    )
    first_code = {
        HealthTrack.MEDICINE: "MED.ANATOMY",
        HealthTrack.PHARMACY: "PHA.CHEMISTRY",
        HealthTrack.NURSING: "NUR.ANATOMY",
    }[track]
    assert graph.missing_prerequisites(first_code, frozenset()) == ()


def test_unknown_track_is_rejected():
    with pytest.raises(ValueError):
        health_profile("clinical-treatment")


def test_independent_tenant_identifiers():
    graph = demonstration_health_graph(
        tenant_id="university-1", curriculum_id="demo-2026",
        track=HealthTrack.MEDICINE,
    )
    assert graph.tenant_id == "university-1"
    assert graph.curriculum_id == "demo-2026"
