from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, StringConstraints

# ---------- Users and auth ----------

WorkspaceRole = Literal["Admin", "Member"]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: str
    name: str
    created_at: datetime


class UserUpdate(BaseModel):
    email: EmailStr = Field(default=None, max_length=255)
    username: str = Field(default=None, min_length=1, max_length=64)
    name: str = Field(default=None, min_length=1, max_length=255)


class MyWorkspace(BaseModel):
    id: int
    name: str
    slug: str
    role: str


class MeOut(UserOut):
    workspaces: list[MyWorkspace]


class GoogleAuthRequest(BaseModel):
    token: str  # the ID token ("credential") from the Sign in with Google button
    # Only for a new account, sent after the app answered signup_required. Email comes from Google.
    # No role: a role belongs to a workspace membership, not the account. Only an Admin can promote someone (PATCH /w/{slug}/members/{id}).
    username: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=255)  # optional; defaults to the Google name


class GoogleSignupRequired(BaseModel):
    """No account for this Google user yet: ask for a username, then send the token again with it."""
    signup_required: Literal[True] = True
    email: str
    name: str  # Google's display name, to prefill the form


class RefreshRequest(BaseModel):
    refresh_token: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginResponse(Token):
    refresh_token: str
    user: UserOut


# Trimmed before the length check, so "Q4 launch " and "Q4 launch" count as the same name.
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


# ---------- Workspaces and members ----------

SLUG = r"^[a-z0-9][a-z0-9-]{2,31}$"


class WorkspaceCreate(BaseModel):
    name: Name
    slug: str = Field(pattern=SLUG)


class WorkspaceUpdate(BaseModel):
    name: Name = None
    slug: str = Field(default=None, pattern=SLUG)


class WorkspaceOut(BaseModel):
    id: int
    name: str
    slug: str
    role: str  # the caller's own role in this workspace
    member_count: int
    created_at: datetime
    updated_at: datetime


class MemberOut(BaseModel):
    user_id: int
    username: str
    name: str
    email: str
    role: str
    joined_at: datetime


class MemberAdd(BaseModel):
    username_or_email: str = Field(min_length=1)
    role: WorkspaceRole = "Member"


class MemberRoleUpdate(BaseModel):
    role: WorkspaceRole  # has to be exactly one of the two roles


# ---------- Teams ----------

TEAM_KEY = r"^[A-Z][A-Z0-9]{1,9}$"


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    name: str
    key: str
    description: str
    is_archived: bool
    issue_count: int  # issues that exist now (set by the router, not a column)
    created_at: datetime
    updated_at: datetime


class TeamCreate(BaseModel):
    name: Name
    key: str = Field(pattern=TEAM_KEY)
    description: str = ""


class TeamUpdate(BaseModel):
    # No key: it's in every issue key (ENG-12) and in links people have shared.
    name: Name = None
    description: str = None
    is_archived: bool = None


class SummaryStats(BaseModel):
    open_issues: int
    completed_issues: int
    active_projects: int
    days_remaining: int | None  # days left in the active sprint; None without one


class TeamSummary(BaseModel):
    team_id: int
    name: str
    active_sprint_id: int | None
    stats: SummaryStats


# ---------- Projects (features / epics) ----------

ProjectStatus = Literal["planned", "in_progress", "paused", "completed", "canceled"]


class ProjectCreate(BaseModel):
    name: Name
    description: str = ""
    status: ProjectStatus = "planned"
    lead_id: int | None = None  # must be a workspace member
    start_date: date | None = None
    target_date: date | None = None


class ProjectUpdate(BaseModel):
    # No team_id: a project stays in its team.
    name: Name = None
    description: str = None
    status: ProjectStatus = None
    lead_id: int | None = None
    start_date: date | None = None
    target_date: date | None = None


class Progress(BaseModel):
    total: int
    done: int


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    name: str
    description: str
    status: str
    lead_id: int | None
    start_date: date | None
    target_date: date | None
    progress: Progress  # set by the router, not a column
    created_at: datetime
    updated_at: datetime


# ---------- Issues ----------

IssueStatus = Literal["todo", "in_progress", "in_review", "done"]
IssueType = Literal["task", "bug", "story"]
Priority = Annotated[int, Field(ge=1, le=5)]  # 1 Highest, 2 High, 3 Medium, 4 Low, 5 Lowest

LabelName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]


def merge_labels(labels: list[str]) -> list[str]:
    """Drop repeats, treating "Bug" and "bug" as the same label; the first spelling wins."""
    merged: list[str] = []
    seen: set[str] = set()
    for label in labels:
        if label.lower() not in seen:
            seen.add(label.lower())
            merged.append(label)
    if len(merged) > 5:
        raise ValueError("An issue can have at most 5 labels")
    return merged


# Each item is trimmed and length-checked first (LabelName), then the whole list is merged and counted.
Labels = Annotated[list[LabelName], AfterValidator(merge_labels)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class IssueCreate(BaseModel):
    # The team comes from the path: POST /w/{slug}/teams/{team_key}/issues
    title: Title
    description: str = ""
    issue_type: IssueType = "task"
    status: IssueStatus = "todo"
    priority: Priority = 3
    assignee_id: int | None = None
    project_id: int | None = None
    sprint_id: int | None = None
    story_points: int = Field(default=0, ge=0)
    labels: Labels = []
    due_date: datetime | None = None


class IssueUpdate(BaseModel):
    # No team_id: moving an issue to another team would change its key.
    title: Title = None
    description: str = None
    issue_type: IssueType = None
    status: IssueStatus = None
    priority: Priority = None
    assignee_id: int | None = None
    project_id: int | None = None
    sprint_id: int | None = None
    story_points: int = Field(default=None, ge=0)
    labels: Labels = None
    due_date: datetime | None = None


class IssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_key: str  # built from the team key and the number (Issue.issue_key property)
    team_id: int
    number: int
    issue_type: str
    project_id: int | None
    sprint_id: int | None
    title: str
    description: str
    status: str
    priority: int
    assignee_id: int | None
    reporter_id: int | None
    story_points: int
    labels: list[str]
    due_date: datetime | None
    created_at: datetime
    updated_at: datetime


class StatusMove(BaseModel):
    status: IssueStatus


class StatusMoveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    issue_key: str
    status: str
    updated_at: datetime


class BulkUpdates(BaseModel):
    """The fields a bulk edit may set, the same for every selected issue."""
    status: IssueStatus = None
    priority: Priority = None
    assignee_id: int | None = None
    project_id: int | None = None
    sprint_id: int | None = None


class BulkUpdateRequest(BaseModel):
    issue_keys: list[str] = Field(min_length=1, max_length=100)
    updates: BulkUpdates


class BulkResult(BaseModel):
    issue_key: str
    status: Literal["Updated", "Failed"]
    updated_at: datetime | None = None
    error: str | None = None


class BulkCounts(BaseModel):
    total: int
    success_count: int
    failure_count: int


class BulkUpdateResponse(BaseModel):
    summary: BulkCounts
    results: list[BulkResult]


class BulkDeleteRequest(BaseModel):
    issue_keys: list[str] = Field(min_length=1, max_length=100)


class BoardColumn(BaseModel):
    id: IssueStatus
    name: str
    issues: list[IssueOut]


class BoardOut(BaseModel):
    team_id: int
    sprint_id: int | None  # the active sprint shown on the board; None = no active sprint
    columns: list[BoardColumn]


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int
    actor_id: int | None
    action: str
    field: str | None
    old_value: Any
    new_value: Any
    created_at: datetime


# ---------- Sprints ----------


class SprintCreate(BaseModel):
    name: Name
    goal: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


class SprintUpdate(BaseModel):
    name: Name = None
    goal: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


class SprintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    name: str
    goal: str | None
    status: str
    start_date: datetime | None
    end_date: datetime | None
    completed_date: datetime | None
    created_by: int | None
    created_at: datetime


class SprintComplete(BaseModel):
    destination_sprint_id: int | None = None  # a planned sprint of the same team; None = backlog


class SprintCompleteOut(BaseModel):
    id: int
    status: str
    completed_date: datetime
    completed_issues: int
    moved_issues: int


class SprintIssuesAdd(BaseModel):
    issue_keys: list[str] = Field(min_length=1, max_length=100)


class SprintIssuesAdded(BaseModel):
    sprint_id: int
    added: list[str]


# ---------- Comments ----------

# Trimmed first, then checked, so a comment of only spaces is rejected.
CommentBody = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class CommentCreate(BaseModel):
    content: CommentBody
    parent_id: int | None = None  # reply to this comment (same issue)


class CommentUpdate(BaseModel):
    content: CommentBody


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int
    author_id: int | None
    parent_id: int | None
    content: str
    is_edited: bool
    created_at: datetime
    updated_at: datetime


# ---------- Views (saved filters) ----------


class IssueFilters(BaseModel):
    """The issue list's filters. Each field is a list of accepted values; a missing field doesn't filter.

    The team issue list builds one from its query parameters, and a view stores one as JSON.
    """
    # extra="forbid": an unknown field ("colour": [...]) is a 422, not silently ignored.
    model_config = ConfigDict(extra="forbid")

    status: list[IssueStatus] | None = None
    priority: list[Priority] | None = None
    issue_type: list[IssueType] | None = None
    assignee_id: list[int] | None = None
    project_id: list[int] | None = None
    sprint_id: list[int] | None = None
    labels: list[str] | None = None


class ViewCreate(BaseModel):
    name: Name
    filters: IssueFilters = IssueFilters()
    is_shared: bool = False


class ViewUpdate(BaseModel):
    name: Name = None
    filters: IssueFilters = None
    is_shared: bool = None


class ViewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    owner_id: int
    name: str
    filters: dict
    is_shared: bool
    created_at: datetime
    updated_at: datetime
