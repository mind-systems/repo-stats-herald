import functools
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
from src.delivery.changelog_client import ChangelogEntry
from src.ingestion.models import InstallationEvent, PushCommit, PushEvent
from src.routing.models import BranchRole
from src.routing.resolver import role_for_branch

router = APIRouter()
logger = logging.getLogger(__name__)

_ENVIRONMENT_BY_ROLE = {BranchRole.STAGING: "staging", BranchRole.RELEASE: "production"}
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


async def _deliver_release(
    event: PushEvent,
    *,
    mirror,
    delivery_plan_resolver,
    versioner,
    build_release_report,
    localizer,
    github_release_client,
    delivery_service,
    changelog_client=None,
) -> None:
    """Cuts the GitHub release and delivers the version-headed Telegram note
    for a staging/release push, resolving the required-language union once
    and building the release note once (`Localizer.report_notes`) so every
    channel is fed from the same localization pass. When the pushed repo is
    mapped to a changelog app and it is reachable, the release note is also
    posted as a `ChangelogEntry` — the last leg of the fan-out, run after the
    GitHub release and the Telegram send.

    The changelog-app leg (`changelog_client` / `plan.changelog_base_url`)
    degrades gracefully: when either is absent, or the app is unreachable at
    `config` or `entry`, the union stays the fixed-channel languages and this
    delivery proceeds without it — an unreachable changelog app never blocks
    the GitHub release or the Telegram delivery.
    """
    role = role_for_branch(event.branch)

    # First, never relying on `knowledge_sync` having ensured — background
    # task order across the registered tasks is not a contract.
    mirror.ensure(event.repo, event.org_id)

    version = versioner.next(event.repo, role, event.before, event.after)
    if version is None:
        # A back-merge/skip case: no staging-unique work, nothing to cut,
        # no version header to send.
        return

    plan = delivery_plan_resolver.resolve(event.org_id, event.repo, event.branch)

    union = {plan.language, plan.github_release_language}
    base_url = getattr(plan, "changelog_base_url", None)
    app_available = changelog_client is not None and bool(base_url)
    declared_languages: list[str] = []
    if app_available:
        try:
            declared_languages = await changelog_client.config(base_url)
            union |= set(declared_languages)
        except Exception:
            logger.exception("changelog app unreachable for repo=%s org_id=%s", event.repo, event.org_id)
            app_available = False

    report = build_release_report(event.repo, event.org_id, event.branch)
    notes = await localizer.report_notes(report, event.repo, event.org_id, union)

    github_url = await github_release_client.create(
        event.org_id,
        event.org_login,
        event.repo,
        version,
        notes.get(plan.github_release_language) or "",
        role is BranchRole.STAGING,
        event.after,
    )
    logger.info("github release created: repo=%s org_id=%s url=%s", event.repo, event.org_id, github_url)

    await delivery_service.deliver(plan, notes.get(plan.language) or "", version=version)

    if app_available:
        try:
            await changelog_client.entry(
                base_url,
                ChangelogEntry(
                    version=str(version),
                    environment=_ENVIRONMENT_BY_ROLE[role],
                    summaries={lang: notes[lang] or "" for lang in declared_languages},
                    github_url=github_url,
                ),
            )
        except Exception:
            logger.exception(
                "changelog entry failed for repo=%s org_id=%s", event.repo, event.org_id
            )


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
            state = request.app.state
            collaborators = {
                "mirror": getattr(state, "mirror", None),
                "delivery_plan_resolver": getattr(state, "delivery_plan_resolver", None),
                "versioner": getattr(state, "versioner", None),
                "build_release_report": getattr(state, "build_release_report", None),
                "localizer": getattr(state, "localizer", None),
                "github_release_client": getattr(state, "github_release_client", None),
                "delivery_service": getattr(state, "delivery_service", None),
            }
            if all(value is not None for value in collaborators.values()):
                task = functools.partial(
                    _deliver_release,
                    changelog_client=getattr(state, "changelog_client", None),
                    **collaborators,
                )
                background_tasks.add_task(_run_isolated, "release_delivery", task, event)
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
