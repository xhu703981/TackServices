from fastapi import APIRouter, Depends, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import GoogleAuthRequest, GoogleSignupRequired, LoginResponse, RefreshRequest, Token, UserOut
from app.security import create_token, user_from_token

router = APIRouter(prefix="/auth", tags=["auth"])

# Reused across requests: it caches Google's public signing keys instead of downloading them every time.
google_transport = google_requests.Request()


def login_response(user: User) -> LoginResponse:
    return LoginResponse(
        access_token=create_token(user.id, "access"),
        refresh_token=create_token(user.id, "refresh"),
        expires_in=settings.jwt_access_expire,
        user=UserOut.model_validate(user),
    )


@router.post("/google", response_model=LoginResponse | GoogleSignupRequired)
def google_auth(payload: GoogleAuthRequest, db: Session = Depends(get_db)):
    """Log in with a Google ID token (the "credential" the Sign in with Google button returns).

    Known user → tokens. New user without a username → signup_required, so the app can ask for one and send the
    same Google token again with username (and name) to create the account.
    """
    try:
        # Checks Google's signature, expiry, and that the token was issued for our client ID.
        claims = id_token.verify_oauth2_token(payload.token, google_transport, settings.google_client_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google token")
    if not claims.get("email_verified"):
        raise HTTPException(status_code=401, detail="Google account email is not verified")
    google_id, email = claims["sub"], claims["email"].lower()

    user = db.scalars(select(User).where(User.auth_provider == "google", User.auth_provider_id == google_id)).first()
    if user is not None:
        return login_response(user)

    # Not linked yet: an account made before Google login (password era) links by its email.
    user = db.scalars(select(User).where(User.email == email)).first()
    if user is not None:
        # Only an unlinked account may be claimed; one tied to another Google account keeps its owner.
        if user.auth_provider is not None:
            raise HTTPException(status_code=409, detail="This email belongs to another account")
        user.auth_provider, user.auth_provider_id = "google", google_id
        db.commit()
        return login_response(user)

    if payload.username is None:
        return GoogleSignupRequired(email=email, name=claims.get("name", ""))

    # A new account belongs to no workspace yet: it creates one (and is its Admin) or gets added to one.
    user = User(
        email=email,
        username=payload.username,
        name=payload.name or claims.get("name") or payload.username,
        auth_provider="google",
        auth_provider_id=google_id,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # The unique index decides, not a check-then-insert: two sign-ups at the same moment can't both win.
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already taken")
    db.refresh(user)
    return login_response(user)


@router.post("/refresh", response_model=Token)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    # Pure JWT: nothing is stored, so logout just means the client deletes both tokens.
    user = user_from_token(db, payload.refresh_token, "refresh")
    return Token(access_token=create_token(user.id, "access"), expires_in=settings.jwt_access_expire)
