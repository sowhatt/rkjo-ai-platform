"""Capability catalog for RKJO Family.

Sprint 0 declares the public domain contracts without implementing the
cross-domain agents. Routing remains capability-first so the platform registry
can resolve concrete agents later.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FamilyCapability:
    name: str
    description: str
    sprint: int


FAMILY_CAPABILITIES: tuple[FamilyCapability, ...] = (
    FamilyCapability(
        name="family.management",
        description="Manage households, members, roles and permissions.",
        sprint=0,
    ),
    FamilyCapability(
        name="family.calendar",
        description="Manage and consolidate household calendar events.",
        sprint=2,
    ),
    FamilyCapability(
        name="family.reminder",
        description="Create tenant-scoped family reminders.",
        sprint=1,
    ),
    FamilyCapability(
        name="document.understanding",
        description="Extract family actions and deadlines from documents.",
        sprint=3,
    ),
    FamilyCapability(
        name="education.tutoring",
        description="Reuse RKJO Education for child tutoring workflows.",
        sprint=4,
    ),
    FamilyCapability(
        name="family.advice",
        description="Identify potentially forgotten family obligations.",
        sprint=6,
    ),
)


def capability_names() -> tuple[str, ...]:
    """Return stable capability names for registry/bootstrap code."""

    return tuple(capability.name for capability in FAMILY_CAPABILITIES)
