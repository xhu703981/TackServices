"""Issue history: every create and every changed field writes one issue_activities row.

The rows are added to the same session as the change, so they commit (or roll back) together:
the history can never disagree with the issue.
"""

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.models import Issue, IssueActivity, User


def record_created(db: Session, issue: Issue, actor: User):
    db.add(IssueActivity(issue_id=issue.id, actor_id=actor.id, action="created"))


def apply_changes(db: Session, issue: Issue, changes: dict, actor: User):
    """Set each field on the issue and record it. A field sent with its current value records nothing."""
    for field, value in changes.items():
        old = getattr(issue, field)
        if old == value:
            continue
        db.add(IssueActivity(
            issue_id=issue.id, actor_id=actor.id, action="updated", field=field,
            # jsonable_encoder turns dates into ISO strings, which JSONB can store.
            old_value=jsonable_encoder(old), new_value=jsonable_encoder(value),
        ))
        setattr(issue, field, value)
