"""Projects and targets — api-contract.md#projects, #targets."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select

from packages.schemas.python.entities import Project as ProjectSchema
from packages.schemas.python.entities import Target as TargetSchema

from ..db import models as m
from ..deps import AppSettings, DbSession, require_auth
from ..errors import forbidden_target, not_found, unprocessable
from ..schemas import (
    CreateProjectRequest,
    CreateTargetRequest,
    ErrorResponse,
    ProjectSummaryResponse,
    from_orm,
)

router = APIRouter(prefix="/api", tags=["projects"], dependencies=[Depends(require_auth)])

ERRORS: dict[int | str, dict] = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.post(
    "/projects",
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
def create_project(body: CreateProjectRequest, db: DbSession) -> ProjectSchema:
    project = m.Project(name=body.name, description=body.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return from_orm(ProjectSchema, project)


@router.get(
    "/projects/{project_id}",
    response_model=ProjectSummaryResponse,
    responses=ERRORS,
)
def get_project(project_id: UUID, db: DbSession) -> ProjectSummaryResponse:
    project = db.get(m.Project, project_id)
    if project is None:
        raise not_found("Project", project_id)

    target_count = db.scalar(
        select(func.count()).select_from(m.Target).where(m.Target.project_id == project_id)
    )
    latest_status = db.scalar(
        select(m.Investigation.status)
        .where(m.Investigation.project_id == project_id)
        .order_by(m.Investigation.created_at.desc())
        .limit(1)
    )

    return ProjectSummaryResponse(
        **{c.name: getattr(project, c.name) for c in m.Project.__table__.columns},
        target_count=target_count or 0,
        latest_investigation_status=latest_status.value if latest_status else None,
    )


@router.post(
    "/projects/{project_id}/targets",
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
def create_target(
    project_id: UUID,
    body: CreateTargetRequest,
    db: DbSession,
    settings: AppSettings,
) -> TargetSchema:
    """Register a target, enforcing both authorization gates.

    security-model.md requires two *independent* checks, and the order
    matters for what a caller learns: confirmation is validated first (422),
    then the allow-list (403). An unconfirmed request for a disallowed host
    is told about the confirmation it forgot, not about which hosts the
    operator has allow-listed.
    """
    if db.get(m.Project, project_id) is None:
        raise not_found("Project", project_id)

    if not body.authorization_confirmed:
        raise unprocessable(
            "authorization_not_confirmed",
            "authorization_confirmed must be true to create a target.",
            {"hint": "There is no unconfirmed-but-created state; see security-model.md."},
        )

    if not settings.host_is_allowed(body.base_url):
        raise forbidden_target(body.base_url)

    target = m.Target(
        project_id=project_id,
        base_url=body.base_url,
        name=body.name,
        authorization_confirmed=True,
        authorization_confirmed_by=body.authorization_confirmed_by,
        # Recorded server-side, not taken from the request: a
        # client-supplied timestamp on an audit field is worth nothing.
        authorization_confirmed_at=datetime.now(UTC),
    )
    db.add(target)
    db.commit()
    db.refresh(target)
    return from_orm(TargetSchema, target)
