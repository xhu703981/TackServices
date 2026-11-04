from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.access import Ctx, get_issue, get_team, is_member, team_ids, workspace_ctx
from app.activity import apply_changes, record_created
from app.database import get_db
from app.models import Issue, IssueActivity, Project, Sprint, Team
from app.schemas import (
    ActivityOut, BulkCounts, BulkDeleteRequest, BulkResult, BulkUpdateRequest, BulkUpdateResponse, IssueCreate,
    IssueOut, IssueUpdate, StatusMove, StatusMoveOut,
)

router = APIRouter(prefix="/w/{slug}", tags=["issues"])


class Invalid(Exception):
    """A rule the issue's final state breaks; the single endpoints answer 422, bulk reports it per issue."""


def check_links(db: Session, ctx: Ctx, issue: Issue, fields: dict):
    """Check the issue as it would be after `fields` are applied (current values + changes).

    - the assignee is a member of the workspace
    - the project belongs to the same team
    - the sprint belongs to the same team and isn't completed
    """
    final = {name: fields.get(name, getattr(issue, name, None)) for name in ("assignee_id", "project_id", "sprint_id")}

    if final["assignee_id"] is not None and not is_member(db, ctx, final["assignee_id"]):
        raise Invalid("Assignee is not a member of this workspace")

    if final["project_id"] is not None:
        project = db.get(Project, final["project_id"])
        if project is None or project.team_id != issue.team_id:
            raise Invalid("Project must belong to the same team")

    if final["sprint_id"] is not None and final["sprint_id"] != issue.sprint_id:
        sprint = db.get(Sprint, final["sprint_id"])
        if sprint is None or sprint.team_id != issue.team_id or sprint.status == "completed":
            raise Invalid("Sprint must be a planned or active sprint of the same team")


def checked(db: Session, ctx: Ctx, issue: Issue, fields: dict):
    try:
        check_links(db, ctx, issue, fields)
    except Invalid as e:
        raise HTTPException(status_code=422, detail=str(e))


def require_deleter(ctx: Ctx, issue: Issue):
    """The reporter or an Admin may delete an issue."""
    if not (issue.reporter_id == ctx.user.id or ctx.is_admin):
        raise HTTPException(status_code=403, detail="Only the reporter or an Admin can delete an issue")


@router.get("/issues", response_model=list[IssueOut])
def list_issues(assignee_id: int | None = None, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    """Every issue in the workspace, most recently updated first. assignee_id={me} gives "My issues"."""
    query = select(Issue).where(Issue.team_id.in_(team_ids(ctx)))
    if assignee_id is not None:
        query = query.where(Issue.assignee_id == assignee_id)
    return db.scalars(query.order_by(Issue.updated_at.desc())).all()


@router.post("/teams/{team_key}/issues", response_model=IssueOut, status_code=201)
def create_issue(team_key: str, payload: IssueCreate, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    team = get_team(db, ctx, team_key)
    fields = payload.model_dump()
    issue = Issue(team_id=team.id)
    checked(db, ctx, issue, fields)
    for field, value in fields.items():
        setattr(issue, field, value)
    # Bump the team's counter and read the new value in one statement. Postgres locks the team
    # row until we commit, so two people creating issues at once get different numbers.
    issue.number = db.scalar(
        update(Team)
        .where(Team.id == team.id)
        .values(last_issue_number=Team.last_issue_number + 1)
        .returning(Team.last_issue_number)
    )
    issue.reporter_id = ctx.user.id
    db.add(issue)
    db.flush()  # gives the issue its id, which the activity row needs
    record_created(db, issue, ctx.user)
    db.commit()
    db.refresh(issue)
    return issue


# The bulk routes come before /issues/{issue_key}: FastAPI tries routes in order, and "bulk" would
# otherwise be taken as an issue key.
@router.patch("/issues/bulk", response_model=BulkUpdateResponse)
def bulk_update(payload: BulkUpdateRequest, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    """Apply the same changes to many issues. Each issue succeeds or fails on its own."""
    changes = payload.updates.model_dump(exclude_unset=True)
    results: list[BulkResult] = []
    updated: list[Issue] = []
    for key in payload.issue_keys:
        try:
            issue = get_issue(db, ctx, key)
            check_links(db, ctx, issue, changes)
        except HTTPException as e:
            results.append(BulkResult(issue_key=key.upper(), status="Failed", error=e.detail))
            continue
        except Invalid as e:
            results.append(BulkResult(issue_key=issue.issue_key, status="Failed", error=str(e)))
            continue
        apply_changes(db, issue, changes, ctx.user)
        updated.append(issue)
        results.append(BulkResult(issue_key=issue.issue_key, status="Updated"))
    db.commit()
    stamps = {i.issue_key: i.updated_at for i in updated}  # reloaded after commit: the trigger's new value
    for r in results:
        r.updated_at = stamps.get(r.issue_key)
    return BulkUpdateResponse(
        summary=BulkCounts(total=len(results), success_count=len(updated), failure_count=len(results) - len(updated)),
        results=results,
    )


@router.delete("/issues/bulk", status_code=204)
def bulk_delete(payload: BulkDeleteRequest, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    """Delete many issues: all of them, or (if any is missing or not allowed) none of them."""
    issues = [get_issue(db, ctx, key) for key in payload.issue_keys]
    for issue in issues:
        require_deleter(ctx, issue)
    for issue in issues:
        db.delete(issue)
    db.commit()


@router.get("/issues/{issue_key}", response_model=IssueOut)
def read_issue(issue_key: str, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    return get_issue(db, ctx, issue_key)


@router.patch("/issues/{issue_key}", response_model=IssueOut)
def update_issue(issue_key: str, payload: IssueUpdate, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    issue = get_issue(db, ctx, issue_key)
    changes = payload.model_dump(exclude_unset=True)
    #exclude_unset=True means "only include fields that are in model_fields_set.
    checked(db, ctx, issue, changes)
    apply_changes(db, issue, changes, ctx.user)
    db.commit()
    db.refresh(issue)
    return issue


@router.put("/issues/{issue_key}/status", response_model=StatusMoveOut)
def move_status(issue_key: str, payload: StatusMove, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    """The board's drag-and-drop: only the status changes."""
    issue = get_issue(db, ctx, issue_key)
    apply_changes(db, issue, {"status": payload.status}, ctx.user)
    db.commit()
    db.refresh(issue)
    return issue


@router.get("/issues/{issue_key}/activity", response_model=list[ActivityOut])
def issue_activity(issue_key: str, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    """The issue's history, oldest first."""
    issue = get_issue(db, ctx, issue_key)
    query = select(IssueActivity).where(IssueActivity.issue_id == issue.id)
    return db.scalars(query.order_by(IssueActivity.created_at, IssueActivity.id)).all()


@router.delete("/issues/{issue_key}", status_code=204)
def delete_issue(issue_key: str, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    issue = get_issue(db, ctx, issue_key)
    require_deleter(ctx, issue)
    # Its comments and activity go with it (ON DELETE CASCADE).
    db.delete(issue)
    db.commit()
