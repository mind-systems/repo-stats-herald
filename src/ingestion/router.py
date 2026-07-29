import hashlib
import hmac
import json
import logging
from collections.abc import Awaitable, Callable

import fastapi
from fastapi import APIRouter, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from src.commits.collector import EMPTY_TREE_SHA
from src.core.config import get_settings
from src.ingestion.models import InstallationEvent, PushCommit, PushEvent
from src.routing.models import BranchRole
from src.routing.resolver import role_for_branch

router = APIRouter()
logger = logging.getLogger(__name__)

_CREATION_BEFORE_SHA = "0" * 40


async def _run_isolated(label: str, task: Callable[[PushEvent], Awaitable[None]], event: PushEvent) -> None:
    """Runs one push background task in isolation, so its failure cannot abort
    a sibling task queued on the same `BackgroundTasks` (Starlette runs them
    sequentially and stops at the first exception)."""
    try:
        await task(event)
    except Exception:
        logger.exception("push background task failed: %s", label)


async def _run_isolated_backfill(knowledge_sync, repo: str, org_id: int) -> None:
    """Runs one repo's semantic backfill in isolation, so its failure cannot
    abort a sibling repo's backfill queued on the same `BackgroundTasks`
    (Starlette runs them sequentially and stops at the first exception)."""
    try:
        await knowledge_sync.backfill(repo, org_id)
    except Exception:
        logger.exception("backfill failed: repo=%s org_id=%s", repo, org_id)


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
    before = EMPTY_TREE_SHA if payload["before"] == _CREATION_BEFORE_SHA else payload["before"]
    return PushEvent(
        org_id=payload["organization"]["id"],
        org_login=payload["organization"]["login"],
        repo=payload["repository"]["name"],
        branch=payload["ref"].removeprefix("refs/heads/"),
        before=before,
        after=payload["after"],
        commits=commits,
    )


def _parse_installation_event(event_name: str, body: bytes) -> InstallationEvent:
    payload = json.loads(body)
    org_id = payload["installation"]["account"]["id"]

    if event_name == "installation_repositories":
        repos_added = tuple(r["name"] for r in payload.get("repositories_added", []))
        repos_removed = tuple(r["name"] for r in payload.get("repositories_removed", []))
    elif event_name == "installation" and payload.get("action") == "created":
        repos_added = tuple(r["name"] for r in payload.get("repositories", []))
        repos_removed = ()
    else:
        repos_added = ()
        repos_removed = ()

    return InstallationEvent(org_id=org_id, repos_added=repos_added, repos_removed=repos_removed)


@router.post("/webhooks/github")
async def receive_github_webhook(
    request: fastapi.Request, background_tasks: fastapi.BackgroundTasks
) -> Response:
    body = await request.body()
    settings = get_settings()
    header = request.headers.get("X-Hub-Signature-256")
    if not _verify_signature(body, header, settings.github_webhook_secret):
        return Response(status_code=401)

    event_name = request.headers.get("X-GitHub-Event")

    if event_name == "push":
        event = _parse_push_event(body)
        if event.org_id not in settings.serve_allowlist:
            logger.info("org not served: org_id=%s repo=%s", event.org_id, event.repo)
            return Response(status_code=204)

        knowledge_sync = getattr(request.app.state, "knowledge_sync", None)
        if knowledge_sync is not None:
            background_tasks.add_task(_run_isolated, "knowledge_sync.on_push", knowledge_sync.on_push, event)

        episodic_writer = getattr(request.app.state, "episodic_writer", None)
        if episodic_writer is not None:
            background_tasks.add_task(_run_isolated, "episodic_writer.write", episodic_writer.write, event)

        role = role_for_branch(event.branch)
        if role in (BranchRole.STAGING, BranchRole.RELEASE):
            release_delivery = getattr(request.app.state, "release_delivery", None)
            if release_delivery is not None:
                background_tasks.add_task(_run_isolated, "release_delivery", release_delivery.deliver, event)
            else:
                logger.info(
                    "release delivery skipped: required collaborators absent (org_id=%s repo=%s)",
                    event.org_id, event.repo,
                )

        return JSONResponse(content=jsonable_encoder(event))

    if event_name in ("installation", "installation_repositories"):
        installation_event = _parse_installation_event(event_name, body)
        if installation_event.org_id not in settings.serve_allowlist:
            logger.info("org not served: org_id=%s", installation_event.org_id)
            return Response(status_code=204)

        store = request.app.state.served_repo_store
        await store.add(installation_event.org_id, installation_event.repos_added)
        await store.remove(installation_event.org_id, installation_event.repos_removed)

        knowledge_sync = getattr(request.app.state, "knowledge_sync", None)
        if knowledge_sync is not None:
            for repo in installation_event.repos_added:
                background_tasks.add_task(_run_isolated_backfill, knowledge_sync, repo, installation_event.org_id)

        logger.info(
            "served repos updated: org_id=%s added=%d removed=%d",
            installation_event.org_id,
            len(installation_event.repos_added),
            len(installation_event.repos_removed),
        )
        return Response(status_code=204)

    return Response(status_code=204)
