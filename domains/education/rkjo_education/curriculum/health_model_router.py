"""Explicit model-profile selection; no live provider connection in this contract."""
from __future__ import annotations
from dataclasses import dataclass
from rkjo_education.curriculum.health_specializations import HealthTrack, health_profile


@dataclass(frozen=True, slots=True)
class ModelRoute:
    track: HealthTrack
    model_profile: str
    verified_sources_required: bool
    allow_patient_advice: bool


def route_health_tutor(track: HealthTrack | str) -> ModelRoute:
    profile = health_profile(track)
    return ModelRoute(
        track=profile.track,
        model_profile=profile.model_profile,
        verified_sources_required=profile.requires_verified_sources,
        allow_patient_advice=profile.patient_specific_advice_allowed,
    )
