"""Who can see and change what.

Everything except the account and notifications lives inside a workspace, under /w/{slug}/...
One role per workspace (workspace_members.role): Admin | Member. There is no team membership.

- Member: read everything in the workspace; create and edit issues, comments, sprints, projects, views.
- Admin: also workspace settings, members, teams, deleting sprints and other people's issues/comments.

A workspace you're not in (and everything in it) answers 404, not 403, so outsiders can't even
learn that it exists. 403 means "you can see it, but your role can't do this".
"""

from dataclasses import dataclass

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Comment, Issue, Project, Sprint, Team, User, View, Workspace, WorkspaceMember
from app.security import get_current_user


@dataclass
class Ctx:
    """The workspace of the request, the caller, and the caller's role there."""

    workspace: Workspace
    user: User
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "Admin"


def workspace_ctx(slug: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Ctx:
    """Dependency for every /w/{slug}/... route: 404 unless the caller is a member of the workspace."""
    workspace = db.scalars(select(Workspace).where(Workspace.slug == slug)).first()
    member = db.get(WorkspaceMember, (workspace.id, current_user.id)) if workspace else None
    if member is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return Ctx(workspace=workspace, user=current_user, role=member.role)


def require_admin(ctx: Ctx):
    if not ctx.is_admin:
        raise HTTPException(status_code=403, detail="Only workspace Admins can do this")


def team_ids(ctx: Ctx):
    """A subquery of the ids of the workspace's teams (use with .in_())."""
    return select(Team.id).where(Team.workspace_id == ctx.workspace.id)


def get_team(db: Session, ctx: Ctx, team_key: str) -> Team:
    """The workspace's team with this key ("eng" works too), else 404."""
    team = db.scalars(select(Team).where(Team.workspace_id == ctx.workspace.id, Team.key == team_key.upper())).first()
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


def get_issue(db: Session, ctx: Ctx, issue_key: str) -> Issue:
    """The issue with this key ("eng-12" works too) in the workspace, else 404.

    The key isn't stored: "ENG-12" means team ENG of this workspace, issue number 12.
    """
    team_key, _, number = issue_key.upper().rpartition("-")
    issue = None
    if team_key and number.isdigit():
        issue = db.scalars(
            select(Issue)
            .join(Team, Issue.team_id == Team.id)
            .where(Team.workspace_id == ctx.workspace.id, Team.key == team_key, Issue.number == int(number))
        ).first()
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue


def get_sprint(db: Session, ctx: Ctx, sprint_id: int) -> Sprint:
    sprint = db.scalars(select(Sprint).where(Sprint.id == sprint_id, Sprint.team_id.in_(team_ids(ctx)))).first()
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")
    return sprint


def get_project(db: Session, ctx: Ctx, project_id: int) -> Project:
    project = db.scalars(select(Project).where(Project.id == project_id, Project.team_id.in_(team_ids(ctx)))).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def get_comment(db: Session, ctx: Ctx, comment_id: int) -> Comment:
    comment = db.scalars(
        select(Comment)
        .join(Issue, Comment.issue_id == Issue.id)
        .where(Comment.id == comment_id, Issue.team_id.in_(team_ids(ctx)))
    ).first()
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    return comment


def get_view(db: Session, ctx: Ctx, view_id: int) -> View:
    """A view of the workspace that the caller may see: their own, or a shared one. Others' private views are 404."""
    view = db.scalars(select(View).where(View.id == view_id, View.team_id.in_(team_ids(ctx)))).first()
    if view is None or not (view.is_shared or view.owner_id == ctx.user.id):
        raise HTTPException(status_code=404, detail="View not found")
    return view


def is_member(db: Session, ctx: Ctx, user_id: int) -> bool:
    return db.get(WorkspaceMember, (ctx.workspace.id, user_id)) is not None
