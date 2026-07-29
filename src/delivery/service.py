import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from src.delivery.changelog_client import ChangelogClient, ChangelogEntry
from src.delivery.github_release import GitHubReleaseClient
from src.delivery.telegram import TelegramClient
from src.github.mirror import RepoMirror
from src.reasoning.localizer import Localizer
from src.routing.models import BranchRole, DeliveryPlan
from src.routing.resolver import DeliveryPlanResolver, role_for_branch
from src.versioning.versioner import Version, Versioner

if TYPE_CHECKING:
    from src.changelog.report import Report
    from src.ingestion.models import PushEvent

logger = logging.getLogger(__name__)

_ENVIRONMENT_BY_ROLE = {BranchRole.STAGING: "staging", BranchRole.RELEASE: "production"}


class DeliveryService:
    """Sends an already-finished note to the channel resolved on a
    `DeliveryPlan` — transport only, it never builds or localizes the note
    itself. When the plan carries no channel (org unmapped), it logs and
    does nothing rather than guessing a destination."""

    def __init__(self, client: TelegramClient) -> None:
        self._client = client

    async def deliver(self, plan: DeliveryPlan, note: str, version: "Version | None" = None) -> None:
        if plan.telegram_channel is None:
            logger.info("no telegram channel resolved for this delivery, skipping")
            return
        text = f"{version}\n\n{note}" if version is not None else note
        await self._client.send(plan.telegram_channel, text)


class ReleaseDelivery:
    """Cuts the GitHub release and delivers the version-headed Telegram note
    for a staging/release push, resolving the required-language union once
    and building the release note once (`Localizer.report_notes`) so every
    channel is fed from the same localization pass. When the pushed repo is
    mapped to a changelog app and it is reachable, the release note is also
    posted as a `ChangelogEntry` — the last leg of the fan-out, run after the
    GitHub release and the Telegram send.

    The changelog-app leg (`changelog_client` / `plan.changelog_base_url`)
    degrades gracefully: when the app is unreachable at `config` or `entry`,
    the union stays the fixed-channel languages and this delivery proceeds
    without it — an unreachable changelog app never blocks the GitHub
    release or the Telegram delivery.
    """

    def __init__(
        self,
        mirror: RepoMirror,
        delivery_plan_resolver: DeliveryPlanResolver,
        versioner: Versioner,
        build_release_report: "Callable[[str, int, str], Report]",
        localizer: Localizer,
        github_release_client: GitHubReleaseClient,
        delivery_service: DeliveryService,
        changelog_client: ChangelogClient,
    ) -> None:
        self._mirror = mirror
        self._delivery_plan_resolver = delivery_plan_resolver
        self._versioner = versioner
        self._build_release_report = build_release_report
        self._localizer = localizer
        self._github_release_client = github_release_client
        self._delivery_service = delivery_service
        self._changelog_client = changelog_client

    async def deliver(self, event: "PushEvent") -> None:
        role = role_for_branch(event.branch)

        # First, never relying on `knowledge_sync` having ensured — background
        # task order across the registered tasks is not a contract.
        self._mirror.ensure(event.repo, event.org_id)

        version = self._versioner.next(event.repo, role, event.before, event.after)
        if version is None:
            # A back-merge/skip case: no staging-unique work, nothing to cut,
            # no version header to send.
            return

        plan = self._delivery_plan_resolver.resolve(event.org_id, event.repo, event.branch)

        union = {plan.language, plan.github_release_language}
        base_url = plan.changelog_base_url
        app_available = bool(base_url)
        declared_languages: list[str] = []
        if app_available:
            try:
                declared_languages = await self._changelog_client.config(base_url)
                union |= set(declared_languages)
            except Exception:
                logger.exception("changelog app unreachable for repo=%s org_id=%s", event.repo, event.org_id)
                app_available = False

        report = self._build_release_report(event.repo, event.org_id, event.branch)
        notes = await self._localizer.report_notes(report, event.repo, event.org_id, union)

        github_url = await self._github_release_client.create(
            event.org_id,
            event.org_login,
            event.repo,
            version,
            notes.get(plan.github_release_language) or "",
            role is BranchRole.STAGING,
            event.after,
        )
        logger.info("github release created: repo=%s org_id=%s url=%s", event.repo, event.org_id, github_url)

        await self._delivery_service.deliver(plan, notes.get(plan.language) or "", version=version)

        if app_available:
            try:
                await self._changelog_client.entry(
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
