import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, Text, cast, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.access import Ctx, get_team, require_admin, workspace_ctx
from app.database import get_db
from app.models import Issue, Project, Sprint, Team
from app.schemas import (
    BoardColumn, BoardOut, IssueFilters, IssueOut, IssueStatus, IssueType, SummaryStats, TeamCreate, TeamOut,
    TeamSummary, TeamUpdate,
)

router = APIRouter(prefix="/w/{slug}/teams", tags=["teams"])

COLUMNS = [("todo", "To Do"), ("in_progress", "In Progress"), ("in_review", "In Review"), ("done", "Done")]


def with_issue_counts(db: Session, teams: list[Team]) -> list[Team]:
    """Set team.issue_count (issues that exist now) with one GROUP BY query for all of them."""
    counts = dict(
        db.execute(
            select(Issue.team_id, func.count()).where(Issue.team_id.in_([t.id for t in teams])).group_by(Issue.team_id)
        ).all()
    )
    for t in teams:
        t.issue_count = counts.get(t.id, 0)  # a plain attribute, not a column; TeamOut reads it
    return teams


def team_out(db: Session, team: Team) -> Team:
    db.refresh(team)
    return with_issue_counts(db, [team])[0]


def active_sprint(db: Session, team_id: int) -> Sprint | None:
    return db.scalars(select(Sprint).where(Sprint.team_id == team_id, Sprint.status == "active")).first()


def filter_issues(query: Select, filters: IssueFilters, search: str | None = None) -> Select:
    """Narrow an issue query by the list filters (shared by the team issue list and views).

    Each filter is a list of accepted values (status IN ('todo', 'in_progress')); labels match an
    issue that has any of them (labels && ARRAY['infra', 'api']).
    """
    for field in ("status", "priority", "issue_type", "assignee_id", "project_id", "sprint_id"):
        values = getattr(filters, field)
        if values:
            query = query.where(getattr(Issue, field).in_(values))
    if filters.labels:
        query = query.where(Issue.labels.overlap(filters.labels))
    if search:
        # Matches the title, or the key ("eng-12"), ignoring case; the % wildcards mean "contains".
        pattern = f"%{search}%"
        key = Team.key + "-" + cast(Issue.number, Text)
        query = query.join(Team, Issue.team_id == Team.id).where(Issue.title.ilike(pattern) | key.ilike(pattern))
    return query


# ---------- Teams ----------

@router.get("", response_model=list[TeamOut])
def list_teams(ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    teams = db.scalars(select(Team).where(Team.workspace_id == ctx.workspace.id).order_by(Team.id)).all()
    return with_issue_counts(db, list(teams))


@router.post("", response_model=TeamOut, status_code=201)
def create_team(payload: TeamCreate, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    require_admin(ctx)
    team = Team(workspace_id=ctx.workspace.id, **payload.model_dump())
    db.add(team)
    try:
        db.commit()
    except IntegrityError:
        # uq_teams_workspace_id_key: the key is taken in this workspace.
        db.rollback()
        raise HTTPException(status_code=409, detail="Team key already taken in this workspace")
    return team_out(db, team)


@router.get("/{team_key}", response_model=TeamOut)
def read_team(team_key: str, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    return with_issue_counts(db, [get_team(db, ctx, team_key)])[0]


@router.patch("/{team_key}", response_model=TeamOut)
def update_team(team_key: str, payload: TeamUpdate, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    team = get_team(db, ctx, team_key)
    require_admin(ctx)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(team, field, value)
    db.commit()
    return team_out(db, team)


@router.delete("/{team_key}", status_code=204)
def delete_team(team_key: str, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    team = get_team(db, ctx, team_key)
    require_admin(ctx)
    # The database deletes its issues, sprints, projects and views with it (ON DELETE CASCADE).
    db.delete(team)
    db.commit()


# ---------- A team's work ----------

@router.get("/{team_key}/summary", response_model=TeamSummary)
def team_summary(team_key: str, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    team = get_team(db, ctx, team_key)
    done = Issue.status == "done"
    open_count, done_count = db.execute(
        select(func.count().filter(~done), func.count().filter(done)).where(Issue.team_id == team.id)
    ).one()
    active_projects = db.scalar(
        select(func.count()).where(Project.team_id == team.id, Project.status == "in_progress")
    )
    sprint = active_sprint(db, team.id)
    days = None
    if sprint and sprint.end_date:
        days = max(0, math.ceil((sprint.end_date - datetime.now(timezone.utc)).total_seconds() / 86400))
    return TeamSummary(
        team_id=team.id,
        name=team.name,
        active_sprint_id=sprint.id if sprint else None,
        stats=SummaryStats(
            open_issues=open_count, completed_issues=done_count,
            active_projects=active_projects, days_remaining=days,
        ),
    )


@router.get("/{team_key}/backlog", response_model=list[IssueOut])
def team_backlog(team_key: str, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    """Unfinished issues not planned in any sprint, most urgent first."""
    team = get_team(db, ctx, team_key)
    return db.scalars(
        select(Issue)
        .where(Issue.team_id == team.id, Issue.sprint_id.is_(None), Issue.status != "done")
        .order_by(Issue.priority, Issue.number)
    ).all()


@router.get("/{team_key}/board", response_model=BoardOut)
def team_board(team_key: str, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    """The active sprint's issues in one column per status (empty columns when no sprint is active)."""
    team = get_team(db, ctx, team_key)
    sprint = active_sprint(db, team.id)
    issues = []
    if sprint:
        issues = db.scalars(select(Issue).where(Issue.sprint_id == sprint.id).order_by(Issue.priority, Issue.number)).all()
    columns = [
        BoardColumn(id=status, name=name, issues=[i for i in issues if i.status == status])
        for status, name in COLUMNS
    ]
    return BoardOut(team_id=team.id, sprint_id=sprint.id if sprint else None, columns=columns)


@router.get("/{team_key}/issues", response_model=list[IssueOut])
def team_issues(
    team_key: str,
    # Repeat a parameter to accept several values: ?status=todo&status=in_progress
    status: list[IssueStatus] = Query(default=None),
    priority: list[int] = Query(default=None),
    issue_type: list[IssueType] = Query(default=None),
    assignee_id: list[int] = Query(default=None),
    project_id: list[int] = Query(default=None),
    sprint_id: list[int] = Query(default=None),
    labels: list[str] = Query(default=None),
    search: str | None = Query(default=None, max_length=255),
    ctx: Ctx = Depends(workspace_ctx),
    db: Session = Depends(get_db),
):
    """Every issue of the team, newest first, narrowed by any filters given."""
    team = get_team(db, ctx, team_key)
    try:
        filters = IssueFilters(
            status=status, priority=priority, issue_type=issue_type, assignee_id=assignee_id,
            project_id=project_id, sprint_id=sprint_id, labels=labels,
        )
    except ValueError as e:  # e.g. priority=9
        raise HTTPException(status_code=422, detail=str(e))
    query = filter_issues(select(Issue).where(Issue.team_id == team.id), filters, search)
    return db.scalars(query.order_by(Issue.number.desc())).all()
