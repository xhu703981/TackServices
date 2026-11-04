from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.access import Ctx, get_project, get_team, is_member, workspace_ctx
from app.database import get_db
from app.models import Issue, Project
from app.schemas import IssueOut, Progress, ProjectCreate, ProjectOut, ProjectStatus, ProjectUpdate

router = APIRouter(prefix="/w/{slug}", tags=["projects"])


def with_progress(db: Session, projects: list[Project]) -> list[Project]:
    """Set project.progress (its issues: total and done) with one GROUP BY query for all of them."""
    rows = db.execute(
        select(Issue.project_id, func.count(), func.count().filter(Issue.status == "done"))
        .where(Issue.project_id.in_([p.id for p in projects]))
        .group_by(Issue.project_id)
    ).all()
    counts = {project_id: (total, done) for project_id, total, done in rows}
    for p in projects:
        total, done = counts.get(p.id, (0, 0))
        p.progress = Progress(total=total, done=done)  # a plain attribute, not a column; ProjectOut reads it
    return projects


def check_project(db: Session, ctx: Ctx, lead_id: int | None, start: date | None, target: date | None):
    if lead_id is not None and not is_member(db, ctx, lead_id):
        raise HTTPException(status_code=422, detail="The lead must be a member of the workspace")
    # The database has the same CHECK; this turns its error into a clear 422.
    if start and target and target < start:
        raise HTTPException(status_code=422, detail="target_date can't be before start_date")


@router.get("/teams/{team_key}/projects", response_model=list[ProjectOut])
def list_projects(
    team_key: str, status: ProjectStatus | None = None, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)
):
    """The team's projects, soonest target date first (projects without one last)."""
    team = get_team(db, ctx, team_key)
    query = select(Project).where(Project.team_id == team.id)
    if status:
        query = query.where(Project.status == status)
    projects = db.scalars(query.order_by(Project.target_date.asc().nulls_last(), Project.id)).all()
    return with_progress(db, list(projects))


@router.post("/teams/{team_key}/projects", response_model=ProjectOut, status_code=201)
def create_project(team_key: str, payload: ProjectCreate, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    team = get_team(db, ctx, team_key)
    check_project(db, ctx, payload.lead_id, payload.start_date, payload.target_date)
    project = Project(team_id=team.id, **payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return with_progress(db, [project])[0]


@router.get("/projects/{project_id}", response_model=ProjectOut)
def read_project(project_id: int, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    return with_progress(db, [get_project(db, ctx, project_id)])[0]


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, payload: ProjectUpdate, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    project = get_project(db, ctx, project_id)
    changes = payload.model_dump(exclude_unset=True)
    # Check the project as it would be after the change, so a new start_date is compared with the old target_date.
    check_project(
        db, ctx,
        changes.get("lead_id"),
        changes.get("start_date", project.start_date),
        changes.get("target_date", project.target_date),
    )
    for field, value in changes.items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return with_progress(db, [project])[0]


@router.get("/projects/{project_id}/issues", response_model=list[IssueOut])
def project_issues(project_id: int, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    project = get_project(db, ctx, project_id)
    return db.scalars(select(Issue).where(Issue.project_id == project.id).order_by(Issue.priority, Issue.number)).all()


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: int, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    project = get_project(db, ctx, project_id)
    if not (project.lead_id == ctx.user.id or ctx.is_admin):
        raise HTTPException(status_code=403, detail="Only the project's lead or an Admin can delete it")
    # Its issues stay; they just lose the project (issues.project_id is ON DELETE SET NULL).
    db.delete(project)
    db.commit()
