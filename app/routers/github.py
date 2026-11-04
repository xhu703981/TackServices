import hashlib
import hmac
import logging
import time

import jwt
import requests
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from app.config import ENV_FILE, settings

router = APIRouter(prefix="/github", tags=["github"])

# uvicorn's own logger, so these lines show in the server output next to its request log.
log = logging.getLogger("uvicorn.error")

API = "https://api.github.com"
API_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


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


@router.post("/webhook", status_code=204, include_in_schema=False)
async def webhook(
    request: Request,
    x_github_event: str = Header(),
    x_hub_signature_256: str = Header(default=""),
):
    """Every event the GitHub App subscribes to is POSTed here (through smee.io while developing locally)."""
    # GitHub signs the raw body with our webhook secret. Without this check anyone could post fake events.
    # The signature covers the exact bytes, so read them before any JSON parsing.
    body = await request.body()
    expected = "sha256=" + hmac.new(settings.github_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, x_hub_signature_256):  # constant time: no guessing it byte by byte
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    if x_github_event == "pull_request":
        pr, repo = payload["pull_request"], payload["repository"]["full_name"]
        log.info(
            "GitHub: pull_request %s #%s %r (branch %s) in %s",
            payload["action"], pr["number"], pr["title"], pr["head"]["ref"], repo,
        )
        # One comment when a PR opens; later actions (pushes, edits, reviews) stay quiet on GitHub.
        if payload["action"] == "opened":
            message = f"👋 Tack received this pull request (branch `{pr['head']['ref']}`)."
            # requests blocks, so it runs on a worker thread instead of stalling every other request.
            await run_in_threadpool(comment_on_pr, payload["installation"]["id"], repo, pr["number"], message)
            log.info("GitHub: commented on %s#%s", repo, pr["number"])
    else:
        log.info("GitHub: %s event (not handled)", x_github_event)
