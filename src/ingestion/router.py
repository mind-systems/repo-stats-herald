import hashlib
import hmac
import json
import logging

import fastapi
from fastapi import APIRouter, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from src.core.config import get_settings
from src.ingestion.models import PushCommit, PushEvent

router = APIRouter()
logger = logging.getLogger(__name__)


def _verify_signature(body: bytes, header: str | None, secret: str) -> bool:
    if header is None:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(expected, header)
    except TypeError:
        return False


def _parse_push_event(body: bytes) -> PushEvent:
    payload = json.loads(body)
    commits = tuple(
        PushCommit(
            sha=commit["id"],
            message=commit["message"],
            added=tuple(commit["added"]),
            modified=tuple(commit["modified"]),
            removed=tuple(commit["removed"]),
            author=commit["author"]["name"],
        )
        for commit in payload["commits"]
    )
    return PushEvent(
        org_id=payload["organization"]["id"],
        org_login=payload["organization"]["login"],
        repo=payload["repository"]["name"],
        branch=payload["ref"].removeprefix("refs/heads/"),
        before=payload["before"],
        after=payload["after"],
        commits=commits,
    )


@router.post("/webhooks/github")
async def receive_github_webhook(request: fastapi.Request) -> Response:
    body = await request.body()
    settings = get_settings()
    header = request.headers.get("X-Hub-Signature-256")
    if not _verify_signature(body, header, settings.github_webhook_secret):
        return Response(status_code=401)

    if request.headers.get("X-GitHub-Event") != "push":
        return Response(status_code=204)

    event = _parse_push_event(body)
    if event.org_id not in settings.serve_allowlist:
        logger.info("org not served: org_id=%s repo=%s", event.org_id, event.repo)
        return Response(status_code=204)

    return JSONResponse(content=jsonable_encoder(event))
