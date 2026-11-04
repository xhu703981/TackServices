from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.access import Ctx, require_admin, workspace_ctx
from app.database import get_db
from app.models import User, Workspace, WorkspaceMember
from app.schemas import MemberAdd, MemberOut, MemberRoleUpdate, WorkspaceCreate, WorkspaceOut, WorkspaceUpdate
from app.security import get_current_user

router = APIRouter(tags=["workspaces"])


def workspace_out(workspace: Workspace, role: str) -> WorkspaceOut:
    return WorkspaceOut(
        id=workspace.id, name=workspace.name, slug=workspace.slug, role=role,
        member_count=len(workspace.members), created_at=workspace.created_at, updated_at=workspace.updated_at,
    )


def member_out(member: WorkspaceMember, user: User) -> MemberOut:
    return MemberOut(
        user_id=user.id, username=user.username, name=user.name, email=user.email,
        role=member.role, joined_at=member.joined_at,
    )


def lock_workspace(db: Session, ctx: Ctx):
    """Lock the workspace row until commit (SELECT ... FOR UPDATE), so two requests changing its
    members take turns instead of both passing the "last Admin" check."""
    db.execute(select(Workspace.id).where(Workspace.id == ctx.workspace.id).with_for_update())


def get_member(db: Session, ctx: Ctx, user_id: int) -> WorkspaceMember:
    member = db.get(WorkspaceMember, (ctx.workspace.id, user_id))
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    return member


def check_not_last_admin(db: Session, member: WorkspaceMember):
    if member.role != "Admin":
        return
    admins = db.scalar(
        select(func.count()).where(WorkspaceMember.workspace_id == member.workspace_id, WorkspaceMember.role == "Admin")
    )
    if admins == 1:
        raise HTTPException(status_code=409, detail="A workspace needs at least one Admin")


# ---------- Workspaces ----------

@router.get("/workspaces", response_model=list[WorkspaceOut])
def list_workspaces(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == current_user.id)
        .order_by(Workspace.id)
    ).all()
    return [workspace_out(w, role) for w, role in rows]


@router.post("/workspaces", response_model=WorkspaceOut, status_code=201)
def create_workspace(payload: WorkspaceCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Anyone can start a workspace; the creator is its first Admin.
    workspace = Workspace(**payload.model_dump())
    workspace.members.append(WorkspaceMember(user_id=current_user.id, role="Admin"))
    db.add(workspace)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That workspace URL is already taken")
    db.refresh(workspace)
    return workspace_out(workspace, "Admin")


@router.get("/w/{slug}", response_model=WorkspaceOut)
def read_workspace(ctx: Ctx = Depends(workspace_ctx)):
    return workspace_out(ctx.workspace, ctx.role)


@router.patch("/w/{slug}", response_model=WorkspaceOut)
def update_workspace(payload: WorkspaceUpdate, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    require_admin(ctx)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(ctx.workspace, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That workspace URL is already taken")
    db.refresh(ctx.workspace)
    return workspace_out(ctx.workspace, ctx.role)


@router.delete("/w/{slug}", status_code=204)
def delete_workspace(ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    require_admin(ctx)
    # The database deletes its teams, and through them everything inside (ON DELETE CASCADE).
    # The members' accounts stay.
    db.delete(ctx.workspace)
    db.commit()


# ---------- Members ----------

@router.get("/w/{slug}/members", response_model=list[MemberOut])
def list_members(ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    rows = db.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == ctx.workspace.id)
        .order_by(User.name)
    ).all()
    return [member_out(m, u) for m, u in rows]


@router.post("/w/{slug}/members", response_model=MemberOut, status_code=201)
def add_member(payload: MemberAdd, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    require_admin(ctx)
    lock_workspace(db, ctx)
    who = payload.username_or_email.strip()
    user = db.scalars(select(User).where(or_(User.username == who, User.email == who.lower()))).first()
    if user is None:
        raise HTTPException(status_code=422, detail="No user with that username or email")
    if db.get(WorkspaceMember, (ctx.workspace.id, user.id)) is not None:
        raise HTTPException(status_code=409, detail="Already a member")
    member = WorkspaceMember(workspace_id=ctx.workspace.id, user_id=user.id, role=payload.role)
    db.add(member)
    db.commit()
    db.refresh(member)
    return member_out(member, user)


@router.patch("/w/{slug}/members/{user_id}", response_model=MemberOut)
def update_member(
    user_id: int, payload: MemberRoleUpdate, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)
):
    require_admin(ctx)
    lock_workspace(db, ctx)
    member = get_member(db, ctx, user_id)
    if payload.role != "Admin":
        check_not_last_admin(db, member)
    member.role = payload.role
    db.commit()
    db.refresh(member)
    return member_out(member, db.get(User, user_id))


@router.delete("/w/{slug}/members/{user_id}", status_code=204)
def remove_member(user_id: int, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    if user_id != ctx.user.id:  # anyone may leave; removing someone else needs an Admin
        require_admin(ctx)
    lock_workspace(db, ctx)
    member = get_member(db, ctx, user_id)
    check_not_last_admin(db, member)
    # Their issues, comments and assignments stay; only the membership goes.
    db.delete(member)
    db.commit()
