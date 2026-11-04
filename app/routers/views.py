from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.access import Ctx, get_team, get_view, workspace_ctx
from app.database import get_db
from app.models import Issue, View
from app.routers.teams import filter_issues
from app.schemas import IssueFilters, IssueOut, ViewCreate, ViewOut, ViewUpdate

router = APIRouter(prefix="/w/{slug}", tags=["views"])


@router.get("/teams/{team_key}/views", response_model=list[ViewOut])
def list_views(team_key: str, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    """My views of this team, plus everyone's shared ones."""
    team = get_team(db, ctx, team_key)
    query = select(View).where(View.team_id == team.id, or_(View.owner_id == ctx.user.id, View.is_shared))
    return db.scalars(query.order_by(View.name)).all()


@router.post("/teams/{team_key}/views", response_model=ViewOut, status_code=201)
def create_view(team_key: str, payload: ViewCreate, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    team = get_team(db, ctx, team_key)
    view = View(
        team_id=team.id, owner_id=ctx.user.id, name=payload.name, is_shared=payload.is_shared,
        # Only the filters that were set: {"priority": [1, 2]}, not every field with null.
        filters=payload.filters.model_dump(exclude_none=True),
    )
    db.add(view)
    db.commit()
    db.refresh(view)
    return view


@router.get("/views/{view_id}", response_model=ViewOut)
def read_view(view_id: int, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    return get_view(db, ctx, view_id)


@router.patch("/views/{view_id}", response_model=ViewOut)
def update_view(view_id: int, payload: ViewUpdate, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    view = get_view(db, ctx, view_id)
    if view.owner_id != ctx.user.id:
        raise HTTPException(status_code=403, detail="Only the view's owner can change it")
    changes = payload.model_dump(exclude_unset=True)
    if "filters" in changes:
        changes["filters"] = payload.filters.model_dump(exclude_none=True)
    for field, value in changes.items():
        setattr(view, field, value)
    db.commit()
    db.refresh(view)
    return view


@router.delete("/views/{view_id}", status_code=204)
def delete_view(view_id: int, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    view = get_view(db, ctx, view_id)
    if not (view.owner_id == ctx.user.id or ctx.is_admin):
        raise HTTPException(status_code=403, detail="Only the view's owner or an Admin can delete it")
    db.delete(view)
    db.commit()


@router.get("/views/{view_id}/issues", response_model=list[IssueOut])
def view_issues(view_id: int, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    """Run the view: the team's issues matching its saved filters, newest first."""
    view = get_view(db, ctx, view_id)
    query = filter_issues(select(Issue).where(Issue.team_id == view.team_id), IssueFilters(**view.filters))
    return db.scalars(query.order_by(Issue.number.desc())).all()
