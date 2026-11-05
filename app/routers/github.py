import hashlib
import hmac
import logging
import time
from datetime import datetime, timedelta, timezone

import jwt
import requests
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.access import Ctx, require_admin, workspace_ctx
from app.config import ENV_FILE, settings
from app.database import get_db
from app.models import GithubInstallation
from app.schemas import GithubConnect, GithubInstallUrl, GithubStatus
from app.security import ALGORITHM

router = APIRouter(prefix="/github", tags=["github"])
# A workspace's connection to GitHub: Settings → Integrations → GitHub.
workspace_router = APIRouter(prefix="/w/{slug}/integrations/github", tags=["github"])

# uvicorn's own logger, so these lines show in the server output next to its request log.
log = logging.getLogger("uvicorn.error")

API = "https://api.github.com"
API_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


# ---------- Acting as the app ----------

def app_jwt() -> str:
    """Proves "I am this GitHub App": a JWT signed with the app's private key. GitHub accepts at most 10 minutes."""
    now = int(time.time())
    # A relative key path starts at the project root (where .env is); "/" keeps an absolute one as it is.
    private_key = (ENV_FILE.parent / settings.github_private_key_path).read_text()
    # iat is backdated a minute in case this machine's clock runs a little ahead of GitHub's.
    payload = {"iat": now - 60, "exp": now + 540, "iss": str(settings.github_app_id)}
    return jwt.encode(payload, private_key, algorithm="RS256")


def installation_token(installation_id: int) -> str:
    """Trades the app JWT for a 1-hour token that acts inside one installation (its repos, its permissions)."""
    res = requests.post(
        f"{API}/app/installations/{installation_id}/access_tokens",
        headers={**API_HEADERS, "Authorization": f"Bearer {app_jwt()}"},
        timeout=10,
    )
    res.raise_for_status()
    return res.json()["token"]


def comment_on_pr(installation_id: int, repo: str, number: int, body: str) -> None:
    # On GitHub's API a pull request is also an issue, and PR conversation comments are issue comments.
    res = requests.post(
        f"{API}/repos/{repo}/issues/{number}/comments",
        headers={**API_HEADERS, "Authorization": f"Bearer {installation_token(installation_id)}"},
        json={"body": body},
        timeout=10,
    )
    res.raise_for_status()


# ---------- Webhooks ----------

def handle_event(db: Session, event: str, payload: dict) -> None:
    if event == "pull_request":
        pr, repo = payload["pull_request"], payload["repository"]["full_name"]
        log.info(
            "GitHub: pull_request %s #%s %r (branch %s) in %s",
            payload["action"], pr["number"], pr["title"], pr["head"]["ref"], repo,
        )
        # One comment when a PR opens; later actions (pushes, edits, reviews) stay quiet on GitHub.
        if payload["action"] == "opened":
            message = f"👋 Tack received this pull request (branch `{pr['head']['ref']}`)."
            comment_on_pr(payload["installation"]["id"], repo, pr["number"], message)
            log.info("GitHub: commented on %s#%s", repo, pr["number"])
    elif event == "installation" and payload["action"] == "deleted":
        # Uninstalled on GitHub: whichever workspace it served is no longer connected.
        db.execute(delete(GithubInstallation).where(GithubInstallation.installation_id == payload["installation"]["id"]))
        db.commit()
        log.info("GitHub: installation %s deleted, disconnected", payload["installation"]["id"])
    else:
        log.info("GitHub: %s %s event (not handled)", event, payload.get("action", ""))


@router.post("/webhook", status_code=204, include_in_schema=False)
async def webhook(
    request: Request,
    x_github_event: str = Header(),
    x_hub_signature_256: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Every event the GitHub App subscribes to is POSTed here (through smee.io while developing locally)."""
    # GitHub signs the raw body with our webhook secret. Without this check anyone could post fake events.
    # The signature covers the exact bytes, so read them before any JSON parsing.
    body = await request.body()
    expected = "sha256=" + hmac.new(settings.github_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, x_hub_signature_256):  # constant time: no guessing it byte by byte
        raise HTTPException(status_code=401, detail="Invalid signature")
    # The database and GitHub calls block, so they run on a worker thread instead of stalling every other request.
    await run_in_threadpool(handle_event, db, x_github_event, await request.json())


# ---------- Connecting a workspace ----------

def installation_repos(installation_id: int) -> list[str]:
    res = requests.get(
        f"{API}/installation/repositories",
        headers={**API_HEADERS, "Authorization": f"Bearer {installation_token(installation_id)}"},
        params={"per_page": 100},
        timeout=10,
    )
    res.raise_for_status()
    return [r["full_name"] for r in res.json()["repositories"]]


@workspace_router.get("", response_model=GithubStatus)
def github_status(ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    inst = db.get(GithubInstallation, ctx.workspace.id)
    if inst is None:
        return GithubStatus(connected=False)
    # Asked live: repos can be added or removed on GitHub at any time.
    return GithubStatus(connected=True, account=inst.account_login, repositories=installation_repos(inst.installation_id))


@workspace_router.post("/install", response_model=GithubInstallUrl)
def github_install_url(ctx: Ctx = Depends(workspace_ctx)):
    """Where to send the browser to install the app. GitHub hands state back unchanged after the install."""
    require_admin(ctx)
    # Signed, so the redirect back can only connect the workspace (and Admin) that started it, within 10 minutes.
    state = jwt.encode(
        {
            "type": "github_install", "ws": ctx.workspace.id, "sub": str(ctx.user.id),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        },
        settings.jwt_secret_key, algorithm=ALGORITHM,
    )
    return GithubInstallUrl(url=f"https://github.com/apps/{settings.github_app_slug}/installations/new?state={state}")


@workspace_router.post("/connect", response_model=GithubStatus)
def github_connect(payload: GithubConnect, ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    """Called by the frontend's callback page with what GitHub's redirect carried."""
    require_admin(ctx)
    try:
        state = jwt.decode(payload.state, settings.jwt_secret_key, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="This GitHub link expired, connect again")
    if state.get("type") != "github_install" or state.get("ws") != ctx.workspace.id or state.get("sub") != str(ctx.user.id):
        raise HTTPException(status_code=400, detail="This GitHub link was started from another workspace")

    # The installation id came through the browser, so ask GitHub that it's a real installation of our app.
    res = requests.get(
        f"{API}/app/installations/{payload.installation_id}",
        headers={**API_HEADERS, "Authorization": f"Bearer {app_jwt()}"},
        timeout=10,
    )
    if res.status_code == 404:
        raise HTTPException(status_code=400, detail="GitHub doesn't know this installation")
    res.raise_for_status()
    account = res.json()["account"]["login"]

    inst = db.get(GithubInstallation, ctx.workspace.id)
    if inst is not None and inst.installation_id != payload.installation_id:
        raise HTTPException(status_code=409, detail=f"Already connected to {inst.account_login}; disconnect it first")
    if inst is None:
        db.add(GithubInstallation(workspace_id=ctx.workspace.id, installation_id=payload.installation_id, account_login=account))
    else:
        inst.account_login = account  # the same installation again (repos changed on GitHub): keep it, refresh the name
    try:
        db.commit()
    except IntegrityError:
        # The unique installation_id: this installation already serves another workspace.
        db.rollback()
        raise HTTPException(status_code=409, detail="This GitHub installation is connected to another workspace")
    return GithubStatus(connected=True, account=account, repositories=installation_repos(payload.installation_id))


@workspace_router.delete("", status_code=204)
def github_disconnect(ctx: Ctx = Depends(workspace_ctx), db: Session = Depends(get_db)):
    """Forget the connection. The app stays installed on GitHub; its events for this installation are then ignored."""
    require_admin(ctx)
    inst = db.get(GithubInstallation, ctx.workspace.id)
    if inst is not None:
        db.delete(inst)
        db.commit()
