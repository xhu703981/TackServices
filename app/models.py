from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, FetchedValue, ForeignKey, Index, Integer, SmallInteger,
    Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def created_at_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def updated_at_column() -> Mapped[datetime]:
    # The database trigger update_<table>_modtime sets updated_at on every UPDATE (see the baseline
    # migration). FetchedValue tells SQLAlchemy the database changes it, so after an UPDATE it
    # reloads the value instead of keeping the stale one in Python.
    return mapped_column(DateTime(timezone=True), server_default=func.now(), server_onupdate=FetchedValue())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # One Google account maps to exactly one user. Local users have (NULL, NULL), and NULLs never
        # count as equal in a UNIQUE index, so any number of local users is fine.
        Index("ix_users_auth_provider", "auth_provider", "auth_provider_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(Text, unique=True)
    email: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    # Login is Google-only. NULL here = an account from before that, linked by email on its first Google sign-in.
    auth_provider: Mapped[str | None] = mapped_column(Text)
    auth_provider_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()

# Mapped[T] is a generic type annotation from the ORM that marks an attribute as a mapped column.
# SQLAlchemy reads it to infer the SQL type and nullability, and type checkers read it to know the attribute is a query expression on the class and a plain T on an instance.


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        # The URL key in /w/{slug}/...: 3-32 lowercase letters, digits or dashes.
        CheckConstraint("slug ~ '^[a-z0-9][a-z0-9-]{2,31}$'", name="slug_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()

    # Not a column: workspace.members loads this workspace's WorkspaceMember rows. The cascade says they belong
    # to the workspace, so deleting the workspace deletes them (matching ON DELETE CASCADE in the database).
    members: Mapped[list["WorkspaceMember"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", passive_deletes=True
    )


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (
        CheckConstraint("role IN ('Admin', 'Member')", name="role_valid"),
    )

    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    role: Mapped[str] = mapped_column(Text, server_default="Member")
    joined_at: Mapped[datetime] = created_at_column()

    #ondelete="CASCADE". This says what happens to membership rows when the thing they point to is deleted:
    # - When a workspace is deleted, all its membership rows are deleted too. A membership in a workspace that doesn't exist means nothing.
    # - When a user is deleted, their memberships are deleted as well.


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (
        CheckConstraint("key ~ '^[A-Z][A-Z0-9]{1,9}$'", name="key_valid"),
        # Keys are unique per workspace: two workspaces can both have an ENG team. The leading
        # column also serves "teams of a workspace".
        UniqueConstraint("workspace_id", "key", name="uq_teams_workspace_id_key"),
        # Trigram index: fast fuzzy search on the name (WHERE name ILIKE '%migr%').
        Index("ix_teams_name_trgm", "name", postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    key: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="")
    last_issue_number: Mapped[int] = mapped_column(Integer, server_default="0")
    is_archived: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class Sprint(Base):
    __tablename__ = "sprints"
    __table_args__ = (
        CheckConstraint("status IN ('planned', 'active', 'completed')", name="status_valid"),
        CheckConstraint("end_date IS NULL OR start_date IS NULL OR end_date > start_date", name="dates_valid"),
        Index("ix_sprints_team_id_status", "team_id", "status"),
        Index("ix_sprints_team_id_start_date", "team_id", "start_date"),
        # Partial unique index: only rows with status 'active' are in it, so a team can have
        # many planned and completed sprints but at most one active one.
        Index("uq_sprints_one_active", "team_id", unique=True, postgresql_where=text("status = 'active'")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    goal: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, server_default="planned")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class Project(Base):
    """A feature or epic inside a team: the parent that groups related issues."""

    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planned', 'in_progress', 'paused', 'completed', 'canceled')", name="status_valid"
        ),
        CheckConstraint("target_date IS NULL OR start_date IS NULL OR target_date >= start_date", name="dates_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="")
    status: Mapped[str] = mapped_column(Text, server_default="planned")
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    start_date: Mapped[date | None] = mapped_column(Date)
    target_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (
        CheckConstraint("issue_type IN ('task', 'bug', 'story')", name="issue_type_valid"),
        CheckConstraint("status IN ('todo', 'in_progress', 'in_review', 'done')", name="status_valid"),
        CheckConstraint("priority BETWEEN 1 AND 5", name="priority_valid"),
        CheckConstraint("story_points >= 0", name="story_points_valid"),
        CheckConstraint("cardinality(labels) <= 5", name="labels_max_5"),
        # Finds ENG-12 (team ENG, number 12), and serves "issues of a team" (team_id is the leading column).
        UniqueConstraint("team_id", "number", name="uq_issues_team_id_number"),
        Index(
            "ix_issues_embedding", "embedding",
            postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    issue_type: Mapped[str] = mapped_column(Text, server_default="task")
    # The project (feature) this issue belongs to. Deleting the project keeps its issues.
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    # NULL = in the backlog. Deleting a sprint sends its issues back to the backlog.
    sprint_id: Mapped[int | None] = mapped_column(ForeignKey("sprints.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="")
    status: Mapped[str] = mapped_column(Text, server_default="todo")
    priority: Mapped[int] = mapped_column(SmallInteger, server_default="3")
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    reporter_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    story_points: Mapped[int] = mapped_column(Integer, server_default="0")
    labels: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()

    # Loaded with the issue so its key ("ENG-12") can be built without another query.
    team: Mapped[Team] = relationship(lazy="joined")

    @property
    def issue_key(self) -> str:
        return f"{self.team.key}-{self.number}"


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    # Threaded replies. Deleting a comment deletes its replies.
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("comments.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text)
    is_edited: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class IssueActivity(Base):
    """One change to an issue. Rows are only inserted, never updated, so there is no updated_at."""

    __tablename__ = "issue_activities"
    __table_args__ = (
        CheckConstraint("action IN ('created', 'updated')", name="action_valid"),
        # An update names the field it changed; a creation doesn't.
        CheckConstraint("(action = 'updated') = (field IS NOT NULL)", name="field_matches_action"),
        # An issue's history in time order, without a separate sort.
        Index("ix_issue_activities_issue_id_created_at", "issue_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(Text)
    field: Mapped[str | None] = mapped_column(Text)
    # JSONB so one column can hold a status string, a user id or a labels array.
    old_value: Mapped[Any] = mapped_column(JSONB(none_as_null=True), nullable=True)
    new_value: Mapped[Any] = mapped_column(JSONB(none_as_null=True), nullable=True)
    created_at: Mapped[datetime] = created_at_column()


class View(Base):
    """A saved filter over one team's issues."""

    __tablename__ = "views"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    filters: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    is_shared: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()
