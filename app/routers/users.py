from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Workspace, WorkspaceMember
from app.schemas import MeOut, MyWorkspace, UserOut, UserUpdate
from app.security import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=MeOut)
def read_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Each workspace I belong to, with my role there: the frontend's workspace switcher.
    rows = db.execute(
        select(Workspace.id, Workspace.name, Workspace.slug, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == current_user.id)
        .order_by(Workspace.id)
    ).all()
    workspaces = [MyWorkspace(id=r[0], name=r[1], slug=r[2], role=r[3]) for r in rows]
    return MeOut(**UserOut.model_validate(current_user).model_dump(), workspaces=workspaces)
# - Swagger UI never reads your code. It only reads `openapi.json` and draws what that file describes.
# - **Authorize button:** appears when `openapi.json` has a `securitySchemes` section.
# - **Padlock:** appears on each endpoint that has a `security` field.
# - **FastAPI's role:** when you use one of its security classes (`OAuth2PasswordBearer`, `HTTPBearer`, `APIKeyHeader`), FastAPI writes both fields for you. Reading the header manually with `Header()` does the same thing at runtime, but FastAPI doesn't know it's a login, so you get no button and no padlocks.


@router.patch("/me", response_model=UserOut)
def update_me(payload: UserUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    changes = payload.model_dump(exclude_unset=True)
    if "email" in changes:
        changes["email"] = changes["email"].lower()
    for field, value in changes.items():
        setattr(current_user, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email or username already taken")
    db.refresh(current_user)
    return current_user

