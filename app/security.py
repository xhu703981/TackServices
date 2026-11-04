from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

ALGORITHM = "HS256"

# Login is Google-only, so Swagger can't log in by itself: its Authorize button takes an access token you paste
# (get one by signing in through the app, or from the /auth/google response).
# auto_error=False: a missing header becomes our 401 below instead of HTTPBearer's 403.
bearer_scheme = HTTPBearer(auto_error=False)


def create_token(user_id: int, kind: str) -> str:
    """kind is "access" (sent with every request, short-lived) or "refresh" (only trades for a new access token)."""
    seconds = settings.jwt_access_expire if kind == "access" else settings.jwt_refresh_expire
    expire = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    payload = {"sub": str(user_id), "type": kind, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)


def create_access_token(user_id: int) -> str:
    return create_token(user_id, "access")


def user_from_token(db: Session, token: str, kind: str) -> User:
    """The user a valid, unexpired token of this kind belongs to; otherwise 401.

    Checking the kind matters: without it a 7-day refresh token would also work as an access token.
    """
    unauthorized = HTTPException(
        status_code=401,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        raise unauthorized
    if payload.get("type") != kind:
        raise unauthorized
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise unauthorized
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme), db: Session = Depends(get_db)
) -> User:
    return user_from_token(db, credentials.credentials if credentials else "", "access")
