"""Behaviour tests for `_deliver_release`, the module-level fan-out that a
staging/release push registers as one isolated background task: it resolves
the required-language union once, builds the release note once via
`Localizer.report_notes`, cuts a GitHub release, and delivers the
version-headed Telegram note.

Collaborators are driven directly with fakes — no real `RepoMirror`,
`Versioner`, `PivotLocalizer`, `GitHubReleaseClient`, or `DeliveryService` —
and no dependency on the not-yet-built changelog-app concrete types: the
changelog client here is a lightweight stand-in exposing just the
`config(base_url) -> object with .languages` shape the fan-out reads.
"""

from dataclasses import dataclass

from src.ingestion.models import PushEvent
from src.ingestion.router import _deliver_release
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
    """Opaque sentinel — `_deliver_release` never inspects it, only passes
    it through to `localizer.report_notes`."""


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


@dataclass
class FakeChangelogConfig:
    languages: list[str]


class FakeChangelogClient:
    def __init__(self, languages: list[str] | None = None, raises: bool = False) -> None:
        self._languages = languages or []
        self._raises = raises
        self.calls: list[str] = []

    async def config(self, base_url: str) -> FakeChangelogConfig:
        self.calls.append(base_url)
        if self._raises:
            raise RuntimeError("changelog app unreachable")
        return FakeChangelogConfig(self._languages)


def _build_release_report(calls: list[str]):
    def _build(repo: str, org_id: int, branch: str) -> FakeReport:
        calls.append("build_release_report")
        return FakeReport()

    return _build


def _collaborators(
    *,
    branch: str,
    version: Version | None,
    plan: FakePlan,
    notes: dict[str, str | None],
    changelog_client=None,
) -> tuple[list[str], dict]:
    calls: list[str] = []
    mirror = FakeMirror(calls)
    versioner = FakeVersioner(calls, version)
    localizer = FakeLocalizer(calls, notes)
    github_release_client = FakeGitHubReleaseClient()
    delivery_service = FakeDeliveryService()
    kwargs = dict(
        mirror=mirror,
        delivery_plan_resolver=FakePlanResolver(plan),
        versioner=versioner,
        build_release_report=_build_release_report(calls),
        localizer=localizer,
        github_release_client=github_release_client,
        delivery_service=delivery_service,
        changelog_client=changelog_client,
    )
    return calls, kwargs


async def test_one_resolution_feeds_every_channel_with_fixed_union() -> None:
    plan = FakePlan(language="ru", github_release_language="en")
    notes = {"ru": "заметка", "en": "note"}
    calls, kwargs = _collaborators(branch="staging", version=VERSION, plan=plan, notes=notes)

    await _deliver_release(_event("staging"), **kwargs)

    localizer: FakeLocalizer = kwargs["localizer"]
    assert len(localizer.report_notes_calls) == 1
    _, _, _, union = localizer.report_notes_calls[0]
    assert union == {"ru", "en"}

    github_release_client: FakeGitHubReleaseClient = kwargs["github_release_client"]
    [call] = github_release_client.calls
    _, _, _, _, body, _, _ = call
    assert body == notes["en"]

    delivery_service: FakeDeliveryService = kwargs["delivery_service"]
    [(_, note, version)] = delivery_service.calls
    assert note == notes["ru"]
    assert version == VERSION


async def test_union_includes_changelog_app_languages_when_reachable() -> None:
    plan = FakePlan(language="ru", github_release_language="en", changelog_base_url="https://changelog.example")
    notes = {"ru": "note-ru", "en": "note-en", "de": "note-de"}
    changelog_client = FakeChangelogClient(languages=["de"])
    calls, kwargs = _collaborators(
        branch="staging", version=VERSION, plan=plan, notes=notes, changelog_client=changelog_client
    )

    await _deliver_release(_event("staging"), **kwargs)

    localizer: FakeLocalizer = kwargs["localizer"]
    _, _, _, union = localizer.report_notes_calls[0]
    assert union == {"ru", "en", "de"}
    assert changelog_client.calls == ["https://changelog.example"]


async def test_mirror_ensure_runs_before_version_and_report() -> None:
    plan = FakePlan()
    notes = {"ru": "note", "en": "note"}
    calls, kwargs = _collaborators(branch="staging", version=VERSION, plan=plan, notes=notes)

    await _deliver_release(_event("staging"), **kwargs)

    assert calls == [
        "mirror.ensure",
        "versioner.next",
        "build_release_report",
        "localizer.report_notes",
    ]


async def test_staging_role_is_prerelease() -> None:
    plan = FakePlan()
    notes = {"ru": "note", "en": "note"}
    _, kwargs = _collaborators(branch="staging", version=VERSION, plan=plan, notes=notes)
    event = _event("staging")

    await _deliver_release(event, **kwargs)

    github_release_client: FakeGitHubReleaseClient = kwargs["github_release_client"]
    [(org_id, owner, repo, version, _body, prerelease, target_commitish)] = github_release_client.calls
    assert prerelease is True
    assert target_commitish == event.after
    assert owner == event.org_login
    assert org_id == event.org_id
    assert repo == event.repo
    assert version == VERSION


async def test_release_role_is_not_prerelease() -> None:
    plan = FakePlan()
    notes = {"ru": "note", "en": "note"}
    _, kwargs = _collaborators(branch="main", version=VERSION, plan=plan, notes=notes)
    event = _event("main")

    await _deliver_release(event, **kwargs)

    github_release_client: FakeGitHubReleaseClient = kwargs["github_release_client"]
    [(_, _, _, _, _, prerelease, target_commitish)] = github_release_client.calls
    assert prerelease is False
    assert target_commitish == event.after


async def test_none_version_skips_release_and_delivery() -> None:
    plan = FakePlan()
    notes = {"ru": "note", "en": "note"}
    calls, kwargs = _collaborators(branch="staging", version=None, plan=plan, notes=notes)

    await _deliver_release(_event("staging"), **kwargs)

    assert calls == ["mirror.ensure", "versioner.next"]
    assert kwargs["github_release_client"].calls == []
    assert kwargs["delivery_service"].calls == []


async def test_unreachable_changelog_app_still_cuts_release_and_delivers() -> None:
    plan = FakePlan(language="ru", github_release_language="en", changelog_base_url="https://changelog.example")
    notes = {"ru": "note-ru", "en": "note-en"}
    changelog_client = FakeChangelogClient(raises=True)
    calls, kwargs = _collaborators(
        branch="staging", version=VERSION, plan=plan, notes=notes, changelog_client=changelog_client
    )

    await _deliver_release(_event("staging"), **kwargs)

    github_release_client: FakeGitHubReleaseClient = kwargs["github_release_client"]
    assert len(github_release_client.calls) == 1

    delivery_service: FakeDeliveryService = kwargs["delivery_service"]
    [(_, _, version)] = delivery_service.calls
    assert version == VERSION

    localizer: FakeLocalizer = kwargs["localizer"]
    _, _, _, union = localizer.report_notes_calls[0]
    assert union == {"ru", "en"}
