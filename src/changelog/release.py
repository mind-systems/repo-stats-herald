from typing import TYPE_CHECKING

from src.changelog.report import Report
from src.changelog.sections.summary import SummarySection
from src.changelog.windows.since_deploy import SinceDeployWindow
from src.routing.resolver import role_for_branch

if TYPE_CHECKING:
    from src.commits.collector import GitCommitCollector
    from src.episodic.linked_change import LinkedChangeResolver
    from src.github.mirror import RepoMirror
    from src.reasoning.reasoner import Reasoner


def release_report(
    repo: str,
    org_id: int,
    branch: str,
    *,
    mirror: "RepoMirror | None" = None,
    collector: "GitCommitCollector | None" = None,
    resolver: "LinkedChangeResolver | None" = None,
    reasoner: "Reasoner | None" = None,
) -> Report:
    """Build the release note as a `Report`: the summary section alone (a
    release is what shipped, not what remains) over a `SinceDeployWindow`
    anchored on `branch`'s role.

    `repo`/`org_id` are accepted for call-site symmetry with
    `Localizer.report_notes(report, repo, org_id, langs)` / `Report.build`,
    which resolve `repo` lazily at render time — they are not stored on the
    returned `Report`.

    `mirror`/`collector`/`resolver`/`reasoner` are keyword-only and default
    to `None` so the window/section build unwired for equality-only or
    type-checking call sites; the composition root passes the real
    collaborators so `SinceDeployWindow.resolve` / `SummarySection.render`
    can run.
    """
    role = role_for_branch(branch)
    window = SinceDeployWindow(mirror, collector, role)
    section = SummarySection(mirror, resolver, reasoner)
    return Report(window, [section])
