"""RKJO Family HTTP API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from rkjo_api.dependencies import get_database_url
from rkjo_api.identity import get_authenticated_identity
from rkjo_family.household.models import (
    Household,
    HouseholdMember,
    HouseholdRole,
)
from rkjo_family.household.postgres_repository import (
    PostgresHouseholdRepository,
)
from rkjo_family.household.service import HouseholdService


router = APIRouter(prefix="/family", tags=["family"])


class HouseholdCreateRequest(BaseModel):
    household_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=300)
    admin_member_id: str = Field(min_length=1, max_length=200)
    admin_display_name: str = Field(min_length=1, max_length=300)


class HouseholdMemberCreateRequest(BaseModel):
    member_id: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=300)
    role: HouseholdRole
    permissions: list[str] = Field(default_factory=list)


class HouseholdMemberResponse(BaseModel):
    member_id: str
    display_name: str
    role: HouseholdRole
    permissions: list[str]


class HouseholdResponse(BaseModel):
    household_id: str
    name: str
    members: list[HouseholdMemberResponse]


def require_tenant(request: Request) -> str:
    identity = get_authenticated_identity(request)
    if identity.tenant_id is None:
        raise HTTPException(
            status_code=400,
            detail="Authenticated identity must be bound to a tenant.",
        )
    return identity.tenant_id


def get_household_service() -> HouseholdService:
    return HouseholdService(
        PostgresHouseholdRepository(get_database_url())
    )


def to_response(household: Household) -> HouseholdResponse:
    return HouseholdResponse(
        household_id=household.household_id,
        name=household.name,
        members=[
            HouseholdMemberResponse(
                member_id=member.member_id,
                display_name=member.display_name,
                role=member.role,
                permissions=sorted(member.permissions),
            )
            for member in household.members
        ],
    )


@router.post(
    "/households",
    response_model=HouseholdResponse,
    status_code=201,
)
def create_household(
    payload: HouseholdCreateRequest,
    request: Request,
    service: HouseholdService = Depends(get_household_service),
):
    tenant_id = require_tenant(request)

    household = Household(
        household_id=payload.household_id,
        tenant_id=tenant_id,
        name=payload.name,
        members=(
            HouseholdMember(
                member_id=payload.admin_member_id,
                tenant_id=tenant_id,
                household_id=payload.household_id,
                display_name=payload.admin_display_name,
                role=HouseholdRole.PARENT_ADMIN,
                permissions=frozenset({"family.management"}),
            ),
        ),
    )

    try:
        return to_response(service.create(household))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/households",
    response_model=list[HouseholdResponse],
)
def list_households(
    request: Request,
    service: HouseholdService = Depends(get_household_service),
):
    tenant_id = require_tenant(request)
    return [
        to_response(item)
        for item in service.list_households(tenant_id=tenant_id)
    ]


@router.get(
    "/households/{household_id}",
    response_model=HouseholdResponse,
)
def get_household(
    household_id: str,
    request: Request,
    service: HouseholdService = Depends(get_household_service),
):
    tenant_id = require_tenant(request)
    try:
        return to_response(
            service.get(tenant_id=tenant_id, household_id=household_id)
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Household not found.") from exc


@router.post(
    "/households/{household_id}/members",
    response_model=HouseholdResponse,
)
def add_household_member(
    household_id: str,
    payload: HouseholdMemberCreateRequest,
    request: Request,
    service: HouseholdService = Depends(get_household_service),
):
    tenant_id = require_tenant(request)
    member = HouseholdMember(
        member_id=payload.member_id,
        tenant_id=tenant_id,
        household_id=household_id,
        display_name=payload.display_name,
        role=payload.role,
        permissions=frozenset(payload.permissions),
    )

    try:
        return to_response(
            service.add_member(
                tenant_id=tenant_id,
                household_id=household_id,
                member=member,
            )
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Household not found.") from exc
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
