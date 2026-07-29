"""Behaviour tests for `ReleaseDelivery.deliver`, the method a staging/release
push registers as one isolated background task: it resolves the
required-language union once, builds the release note once via
`Localizer.report_notes`, cuts a GitHub release, and delivers the
version-headed Telegram note.

Collaborators are driven directly with fakes — no real `RepoMirror`,
`Versioner`, `PivotLocalizer`, `GitHubReleaseClient`, or `DeliveryService` —
and the changelog client here is a lightweight stand-in exposing the frozen
`config(base_url) -> list[str]` / `entry(base_url, payload) -> None` shape
the fan-out reads and calls.
"""

from dataclasses import dataclass

from src.delivery.service import ReleaseDelivery
from src.ingestion.models import PushEvent
from src.versioning.versioner import Version

ORG_ID = 244165546
ORG_LOGIN = "mind-systems"
REPO = "repo-stats-herald"

VERSION = Version(1, 2, 0, prerelease=True)


def _event(branch: str) -> PushEvent:
    return PushEvent(
        org_id=ORG_ID,
        org_login=ORG_LOGIN,
        repo=REPO,
        branch=branch,
        before="0" * 40,
        after="1" * 40,
        commits=(),
    )


@dataclass
class FakePlan:
    """Stand-in for `DeliveryPlan` extended with the not-yet-built
    `changelog_base_url` field — a plain dataclass rather than the real
    (frozen, field-fixed) `DeliveryPlan`, so these tests don't depend on
    12.1's schema."""

    language: str = "ru"
    github_release_language: str = "en"
    telegram_channel: str | None = "-100123"
    changelog_base_url: str | None = None


class FakeMirror:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def ensure(self, repo: str, org_id: int) -> None:
        self._calls.append("mirror.ensure")


class FakeVersioner:
    def __init__(self, calls: list[str], version: Version | None) -> None:
        self._calls = calls
        self._version = version
        self.next_calls: list[tuple] = []

    def next(self, repo, role, before, after):
        self._calls.append("versioner.next")
        self.next_calls.append((repo, role, before, after))
        return self._version


class FakePlanResolver:
    def __init__(self, plan: FakePlan) -> None:
        self.plan = plan

    def resolve(self, org_id: int, repo: str, branch: str) -> FakePlan:
        return self.plan


class FakeReport:
    """Opaque sentinel — `ReleaseDelivery.deliver` never inspects it, only
    passes it through to `localizer.report_notes`."""


class FakeLocalizer:
    def __init__(self, calls: list[str], notes: dict[str, str | None]) -> None:
        self._calls = calls
        self._notes = notes
        self.report_notes_calls: list[tuple] = []

    async def report_notes(self, report, repo, org_id, langs):
        self._calls.append("localizer.report_notes")
        self.report_notes_calls.append((report, repo, org_id, set(langs)))
        return self._notes


class FakeGitHubReleaseClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def create(self, org_id, owner, repo, version, body, prerelease, target_commitish) -> str:
        self.calls.append((org_id, owner, repo, version, body, prerelease, target_commitish))
        return "https://github.com/example/repo/releases/tag/v1.2.0-rc"


class FakeDeliveryService:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def deliver(self, plan, note, version=None) -> None:
        self.calls.append((plan, note, version))


class FakeChangelogClient:
    def __init__(
        self, languages: list[str] | None = None, raises: bool = False, entry_raises: bool = False
    ) -> None:
        self._languages = languages or []
        self._raises = raises
        self._entry_raises = entry_raises
        self.calls: list[str] = []
        self.entries: list[tuple] = []

    async def config(self, base_url: str) -> list[str]:
        self.calls.append(base_url)
        if self._raises:
            raise RuntimeError("changelog app unreachable")
        return self._languages

    async def entry(self, base_url: str, payload) -> None:
        if self._entry_raises:
            raise RuntimeError("changelog app unreachable at entry")
        self.entries.append((base_url, payload))


def _build_release_report(calls: list[str]):
    def _build(repo: str, org_id: int, branch: str) -> FakeReport:
        calls.append("build_release_report")
        return FakeReport()

    return _build


@dataclass
class Fakes:
    mirror: FakeMirror
    versioner: FakeVersioner
    localizer: FakeLocalizer
    github_release_client: FakeGitHubReleaseClient
    delivery_service: FakeDeliveryService
    changelog_client: FakeChangelogClient


def _collaborators(
    *,
    branch: str,
    version: Version | None,
    plan: FakePlan,
    notes: dict[str, str | None],
    changelog_client: FakeChangelogClient | None = None,
) -> tuple[list[str], ReleaseDelivery, Fakes]:
    calls: list[str] = []
    mirror = FakeMirror(calls)
    versioner = FakeVersioner(calls, version)
    localizer = FakeLocalizer(calls, notes)
    github_release_client = FakeGitHubReleaseClient()
    delivery_service = FakeDeliveryService()
    changelog_client = changelog_client if changelog_client is not None else FakeChangelogClient()
    release_delivery = ReleaseDelivery(
        mirror=mirror,
        delivery_plan_resolver=FakePlanResolver(plan),
        versioner=versioner,
        build_release_report=_build_release_report(calls),
        localizer=localizer,
        github_release_client=github_release_client,
        delivery_service=delivery_service,
        changelog_client=changelog_client,
    )
    fakes = Fakes(
        mirror=mirror,
        versioner=versioner,
        localizer=localizer,
        github_release_client=github_release_client,
        delivery_service=delivery_service,
        changelog_client=changelog_client,
    )
    return calls, release_delivery, fakes


async def test_one_resolution_feeds_every_channel_with_fixed_union() -> None:
    plan = FakePlan(language="ru", github_release_language="en")
    notes = {"ru": "заметка", "en": "note"}
    _, release_delivery, fakes = _collaborators(branch="staging", version=VERSION, plan=plan, notes=notes)

    await release_delivery.deliver(_event("staging"))

    assert len(fakes.localizer.report_notes_calls) == 1
    _, _, _, union = fakes.localizer.report_notes_calls[0]
    assert union == {"ru", "en"}

    [call] = fakes.github_release_client.calls
    _, _, _, _, body, _, _ = call
    assert body == notes["en"]

    [(_, note, version)] = fakes.delivery_service.calls
    assert note == notes["ru"]
    assert version == VERSION


async def test_union_includes_changelog_app_languages_when_reachable() -> None:
    plan = FakePlan(language="ru", github_release_language="en", changelog_base_url="https://changelog.example")
    notes = {"ru": "note-ru", "en": "note-en", "de": "note-de"}
    changelog_client = FakeChangelogClient(languages=["de"])
    _, release_delivery, fakes = _collaborators(
        branch="staging", version=VERSION, plan=plan, notes=notes, changelog_client=changelog_client
    )

    await release_delivery.deliver(_event("staging"))

    _, _, _, union = fakes.localizer.report_notes_calls[0]
    assert union == {"ru", "en", "de"}
    assert changelog_client.calls == ["https://changelog.example"]


async def test_mirror_ensure_runs_before_version_and_report() -> None:
    plan = FakePlan()
    notes = {"ru": "note", "en": "note"}
    calls, release_delivery, _ = _collaborators(branch="staging", version=VERSION, plan=plan, notes=notes)

    await release_delivery.deliver(_event("staging"))

    assert calls == [
        "mirror.ensure",
        "versioner.next",
        "build_release_report",
        "localizer.report_notes",
    ]


async def test_staging_role_is_prerelease() -> None:
    plan = FakePlan()
    notes = {"ru": "note", "en": "note"}
    _, release_delivery, fakes = _collaborators(branch="staging", version=VERSION, plan=plan, notes=notes)
    event = _event("staging")

    await release_delivery.deliver(event)

    [(org_id, owner, repo, version, _body, prerelease, target_commitish)] = fakes.github_release_client.calls
    assert prerelease is True
    assert target_commitish == event.after
    assert owner == event.org_login
    assert org_id == event.org_id
    assert repo == event.repo
    assert version == VERSION


async def test_release_role_is_not_prerelease() -> None:
    plan = FakePlan()
    notes = {"ru": "note", "en": "note"}
    _, release_delivery, fakes = _collaborators(branch="main", version=VERSION, plan=plan, notes=notes)
    event = _event("main")

    await release_delivery.deliver(event)

    [(_, _, _, _, _, prerelease, target_commitish)] = fakes.github_release_client.calls
    assert prerelease is False
    assert target_commitish == event.after


async def test_none_version_skips_release_and_delivery() -> None:
    plan = FakePlan()
    notes = {"ru": "note", "en": "note"}
    calls, release_delivery, fakes = _collaborators(branch="staging", version=None, plan=plan, notes=notes)

    await release_delivery.deliver(_event("staging"))

    assert calls == ["mirror.ensure", "versioner.next"]
    assert fakes.github_release_client.calls == []
    assert fakes.delivery_service.calls == []


async def test_unreachable_changelog_app_still_cuts_release_and_delivers() -> None:
    plan = FakePlan(language="ru", github_release_language="en", changelog_base_url="https://changelog.example")
    notes = {"ru": "note-ru", "en": "note-en"}
    changelog_client = FakeChangelogClient(raises=True)
    _, release_delivery, fakes = _collaborators(
        branch="staging", version=VERSION, plan=plan, notes=notes, changelog_client=changelog_client
    )

    await release_delivery.deliver(_event("staging"))

    assert len(fakes.github_release_client.calls) == 1

    [(_, _, version)] = fakes.delivery_service.calls
    assert version == VERSION

    _, _, _, union = fakes.localizer.report_notes_calls[0]
    assert union == {"ru", "en"}

    assert changelog_client.entries == []


async def test_mapped_reachable_staging_push_posts_changelog_entry() -> None:
    plan = FakePlan(language="ru", github_release_language="en", changelog_base_url="https://changelog.example")
    notes = {"ru": "note-ru", "en": "note-en", "de": "note-de"}
    changelog_client = FakeChangelogClient(languages=["ru", "en", "de"])
    _, release_delivery, fakes = _collaborators(
        branch="staging", version=VERSION, plan=plan, notes=notes, changelog_client=changelog_client
    )

    await release_delivery.deliver(_event("staging"))

    [(_, _, _, _, _, _, _)] = fakes.github_release_client.calls
    github_url = "https://github.com/example/repo/releases/tag/v1.2.0-rc"

    [(base_url, entry)] = changelog_client.entries
    assert base_url == "https://changelog.example"
    assert entry.environment == "staging"
    assert entry.version == str(VERSION)
    assert entry.github_url == github_url
    assert entry.summaries == {"ru": "note-ru", "en": "note-en", "de": "note-de"}


async def test_mapped_release_push_posts_production_changelog_entry() -> None:
    plan = FakePlan(language="ru", github_release_language="en", changelog_base_url="https://changelog.example")
    notes = {"ru": "note-ru", "en": "note-en", "de": "note-de"}
    changelog_client = FakeChangelogClient(languages=["ru", "en", "de"])
    _, release_delivery, _ = _collaborators(
        branch="main", version=VERSION, plan=plan, notes=notes, changelog_client=changelog_client
    )

    await release_delivery.deliver(_event("main"))

    [(_, entry)] = changelog_client.entries
    assert entry.environment == "production"


async def test_unmapped_repo_posts_no_changelog_entry_but_still_delivers() -> None:
    plan = FakePlan(language="ru", github_release_language="en", changelog_base_url=None)
    notes = {"ru": "note-ru", "en": "note-en"}
    changelog_client = FakeChangelogClient(languages=["ru", "en", "de"])
    _, release_delivery, fakes = _collaborators(
        branch="staging", version=VERSION, plan=plan, notes=notes, changelog_client=changelog_client
    )

    await release_delivery.deliver(_event("staging"))

    assert changelog_client.entries == []
    assert changelog_client.calls == []
    assert len(fakes.github_release_client.calls) == 1
    assert len(fakes.delivery_service.calls) == 1


async def test_app_unreachable_at_entry_still_delivered_and_raise_swallowed() -> None:
    plan = FakePlan(language="ru", github_release_language="en", changelog_base_url="https://changelog.example")
    notes = {"ru": "note-ru", "en": "note-en", "de": "note-de"}
    changelog_client = FakeChangelogClient(languages=["ru", "en", "de"], entry_raises=True)
    _, release_delivery, fakes = _collaborators(
        branch="staging", version=VERSION, plan=plan, notes=notes, changelog_client=changelog_client
    )

    await release_delivery.deliver(_event("staging"))

    assert len(fakes.github_release_client.calls) == 1
    assert len(fakes.delivery_service.calls) == 1
    assert changelog_client.entries == []


async def test_changelog_entry_reuses_config_and_report_notes_without_re_deriving() -> None:
    plan = FakePlan(language="ru", github_release_language="en", changelog_base_url="https://changelog.example")
    notes = {"ru": "note-ru", "en": "note-en", "de": "note-de"}
    changelog_client = FakeChangelogClient(languages=["ru", "en", "de"])
    _, release_delivery, fakes = _collaborators(
        branch="staging", version=VERSION, plan=plan, notes=notes, changelog_client=changelog_client
    )

    await release_delivery.deliver(_event("staging"))

    assert len(changelog_client.entries) == 1
    assert len(changelog_client.calls) == 1
    assert len(fakes.localizer.report_notes_calls) == 1
