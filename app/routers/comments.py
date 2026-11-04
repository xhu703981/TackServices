from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import Ctx, get_comment, get_issue, workspace_ctx
from app.database import get_db
from app.models import Comment
from app.schemas import CommentCreate, CommentOut, CommentUpdate

router = APIRouter(prefix="/w/{slug}", tags=["comments"])


@router.get("/issues/{issue_key}/comments", response_model=list[CommentOut])
def list_comments(issue_key: str, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    """Oldest first, flat. Replies carry parent_id, so the client can nest them into threads."""
    issue = get_issue(db, ctx, issue_key)
    query = select(Comment).where(Comment.issue_id == issue.id).order_by(Comment.created_at, Comment.id)
    return db.scalars(query).all()


@router.post("/issues/{issue_key}/comments", response_model=CommentOut, status_code=201)
def create_comment(
    issue_key: str, payload: CommentCreate, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)
):
    issue = get_issue(db, ctx, issue_key)
    if payload.parent_id is not None:
        parent = db.get(Comment, payload.parent_id)
        if parent is None or parent.issue_id != issue.id:
            raise HTTPException(status_code=422, detail="You can only reply to a comment on the same issue")
    comment = Comment(issue_id=issue.id, author_id=ctx.user.id, **payload.model_dump())
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.patch("/comments/{comment_id}", response_model=CommentOut)
def update_comment(
    comment_id: int, payload: CommentUpdate, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)
):
    comment = get_comment(db, ctx, comment_id)
    if comment.author_id != ctx.user.id:
        raise HTTPException(status_code=403, detail="Only the author can edit a comment")
    comment.content = payload.content
    comment.is_edited = True
    db.commit()
    db.refresh(comment)
    return comment


@router.delete("/comments/{comment_id}", status_code=204)
def delete_comment(comment_id: int, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    comment = get_comment(db, ctx, comment_id)
    if not (comment.author_id == ctx.user.id or ctx.is_admin):
        raise HTTPException(status_code=403, detail="Only the author or an Admin can delete a comment")
    # Replies to it go too (comments.parent_id is ON DELETE CASCADE).
    db.delete(comment)
    db.commit()
