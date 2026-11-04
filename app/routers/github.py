import hashlib
import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Request

from app.config import settings

router = APIRouter(prefix="/github", tags=["github"])

# uvicorn's own logger, so these lines show in the server output next to its request log.
log = logging.getLogger("uvicorn.error")


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
        pr = payload["pull_request"]
        log.info(
            "GitHub: pull_request %s #%s %r (branch %s) in %s",
            payload["action"], pr["number"], pr["title"], pr["head"]["ref"], payload["repository"]["full_name"],
        )
    else:
        log.info("GitHub: %s event (not handled)", x_github_event)
