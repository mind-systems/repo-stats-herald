import re
import subprocess
from datetime import datetime

from src.commits.models import Commit, CommitContext

# Literal git placeholder text for the --pretty=format argument: git itself expands
# %x1e/%x00 into actual RS/NUL bytes in its output. These must stay literal text here —
# embedding real NUL bytes in the CLI argument would break process creation.
_PRETTY_FORMAT = "%x1e%H%x00%an%x00%s%x00%b%x00"

# Actual RS/NUL bytes as they appear in git's stdout, used to split the output above.
_RECORD_SEP = "\x1e"
_FIELD_SEP = "\x00"

_NUMSTAT_RE = re.compile(r"^(?:\d+|-)\t(?:\d+|-)\t(.+)$")
_SHORTSTAT_RE = re.compile(r"^\s*\d+ files? changed\b.*$")

# The SHA of the empty tree, constant across every git repo. Used as the
# synthetic `before` of a history's root commit: `git log <empty-tree>..X`
# and `git show <empty-tree>:<path>` behave as "nothing existed yet" without
# any special-casing in callers that walk history step by step.
EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


class GitCommitCollector:
    """Reads commit history from a local git repo (read-only) into domain objects."""

    def __init__(self, git_bin: str = "git") -> None:
        self._git_bin = git_bin

    def collect(self, repo_path: str, rev_range: str) -> CommitContext:
        branch = self._current_branch(repo_path)
        commits = self._collect_commits(repo_path, rev_range)
        return CommitContext(repo=repo_path, branch=branch, commits=commits)

    def first_parent_steps(self, repo_path: str, ref: str) -> list[tuple[str, str]]:
        """Enumerate `ref`'s first-parent history oldest-first as `(before,
        after)` SHA pairs, one per step. The root commit's `before` is the
        empty-tree SHA (no prior state). Read-only; a repo with an unborn
        `HEAD` or an unknown `ref` yields `[]` rather than raising.
        """
        result = subprocess.run(
            [
                self._git_bin,
                "-C",
                repo_path,
                "rev-list",
                "--reverse",
                "--first-parent",
                "--parents",
                "--end-of-options",
                ref,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return []

        steps: list[tuple[str, str]] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            shas = line.split()
            after = shas[0]
            before = shas[1] if len(shas) > 1 else EMPTY_TREE_SHA
            steps.append((before, after))
        return steps

    def changed_paths(self, repo_path: str, before: str, after: str) -> tuple[str, ...]:
        """List paths changed between `before` and `after`, read-only.

        Runs a two-tree diff (`--no-renames` so rename arrows don't corrupt
        paths), which does not fail on merge commits. An unknown/unborn ref
        yields `()` rather than raising, mirroring `first_parent_steps`'
        no-raise contract. `core.quotepath=false` keeps non-ASCII path bytes
        literal instead of quoted/octal-escaped, so such paths still match
        `SourceStrategy.selects` and resolve via `read_blob`.
        """
        result = subprocess.run(
            [
                self._git_bin,
                "-c",
                "core.quotepath=false",
                "-C",
                repo_path,
                "diff",
                "--name-only",
                "--no-renames",
                "--end-of-options",
                before,
                after,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return ()
        return tuple(line for line in result.stdout.splitlines() if line.strip())

    def read_blob(self, repo_path: str, ref: str, path: str) -> str | None:
        """Read `path`'s blob content at `ref` directly from the object
        store, or `None` if the path is absent at that ref or its content
        isn't valid UTF-8.

        Bytes are captured (not `text=True`) and decoded manually: with
        `text=True`, an invalid-UTF-8 blob would raise inside
        `subprocess.run` before this method's guard could turn it into
        `None`.
        """
        result = subprocess.run(
            [self._git_bin, "-C", repo_path, "show", "--end-of-options", f"{ref}:{path}"],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        try:
            return result.stdout.decode("utf-8")
        except UnicodeDecodeError:
            return None

    def active_branches(self, repo_path: str, before: str, after: str) -> list[tuple[str, str, str]]:
        """Enumerate the branches active in `before`..`after`'s time window.

        The window boundary is derived from the two commits' own dates
        (`commit_timestamp`, `git show -s --format=%cI`) rather than the ref
        names themselves. Returns one `(branch, branch_before, branch_after)`
        triple per branch with at least one commit in `[before_time,
        after_time]` (`git rev-list --since=<before_time>
        --until=<after_time> <branch>`, newest-first) — a branch with none in
        that span is inactive and skipped rather than yielding an empty
        triple. `branch_after` is the newest in-window SHA; `branch_before`
        is the branch's own tip at or before `before_time` (`git rev-list -1
        --until=<before_time> <branch>`), falling back to the empty-tree SHA
        when the branch predates that boundary.

        Read-only and no-raise for the per-branch enumeration itself
        (`for-each-ref`/`rev-list` failures or an inactive branch just yield
        no triple for it, mirroring `first_parent_steps`'/`changed_paths`'
        `check=False` contract) — `before`/`after` are assumed-valid refs
        already resolved by the caller, same precondition `commit_timestamp`
        and `collect` rely on.

        Empty-tree-safe on both boundaries: `commit_timestamp` runs `git
        show -s --format=%cI` on the ref, which prints a tree header (not a
        commit date) for the empty-tree SHA and would otherwise raise inside
        `datetime.fromisoformat`. A caller resolving a report window can
        legitimately hand this method `after == EMPTY_TREE_SHA` (an empty
        repo — no branch can be active, so this returns `[]` before either
        timestamp lookup) or `before == EMPTY_TREE_SHA` with a real `after`
        (a young repo whose whole in-window history predates any prior
        commit — treated as "beginning of time": no `--since` filter, and
        every active branch's `branch_before` is the empty-tree SHA).
        """
        if after == EMPTY_TREE_SHA:
            return []

        after_time = self.commit_timestamp(repo_path, after).isoformat()

        if before == EMPTY_TREE_SHA:
            before_time: str | None = None
        else:
            before_time = self.commit_timestamp(repo_path, before).isoformat()

        branches: list[tuple[str, str, str]] = []
        for branch in self._branch_names(repo_path):
            since_args = [f"--since={before_time}"] if before_time is not None else []
            in_window = self._rev_list(
                repo_path, *since_args, f"--until={after_time}", ref=branch
            )
            if not in_window:
                continue
            branch_after = in_window[0]

            if before_time is None:
                branch_before = EMPTY_TREE_SHA
            else:
                at_or_before = self._rev_list(repo_path, "-1", f"--until={before_time}", ref=branch)
                branch_before = at_or_before[0] if at_or_before else EMPTY_TREE_SHA

            branches.append((branch, branch_before, branch_after))
        return branches

    def commit_at_or_before(self, repo_path: str, ref: str, when: datetime) -> str | None:
        """Return the newest commit on `ref` at or before `when`, or `None`
        when `ref` has no commit at or before that timestamp. Read-only and
        no-raise (`check=False`), same contract as the other enumeration
        primitives."""
        matches = self._rev_list(repo_path, "-1", f"--until={when.isoformat()}", ref=ref)
        return matches[0] if matches else None

    def list_tags(self, repo_path: str) -> tuple[str, ...]:
        """List every tag in the repo, verbatim and parse-agnostic (`git
        tag`) — non-version tags (`nightly`, `build-42`, …) are NOT filtered
        here; that is the semver-parsing caller's job (`Version.parse`).
        Read-only and no-raise: an empty tuple on non-zero exit."""
        result = subprocess.run(
            [self._git_bin, "-C", repo_path, "tag"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return ()
        return tuple(line for line in result.stdout.splitlines() if line.strip())

    def is_ancestor(self, repo_path: str, sha: str, ref: str) -> bool:
        """Whether `sha` (which may itself be a tag name/ref) is an ancestor
        of `ref` (`git merge-base --is-ancestor`). Read-only and no-raise:
        exit 0 -> `True`, any non-zero exit (including an unknown ref) ->
        `False`."""
        result = subprocess.run(
            [self._git_bin, "-C", repo_path, "merge-base", "--is-ancestor", "--end-of-options", sha, ref],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0

    def new_commits(self, repo_path: str, before: str, after: str, exclude_ref: str) -> tuple[str, ...]:
        """Non-merge commits `before..after` introduces that are not already
        reachable from `exclude_ref` (`git rev-list <before>..<after>
        --no-merges --not <exclude_ref>`). `--no-merges` drops the merge
        commit itself and excluding `exclude_ref` drops anything already
        reachable from it, so a fast-forward OR merge-commit back-merge that
        pulls `exclude_ref` down with no unique non-merge work yields an
        empty tuple. Read-only and no-raise: an empty tuple on non-zero
        exit.

        The exclusion is written as a literal `^exclude_ref` argument rather
        than the `--not` flag so `--end-of-options` can precede BOTH
        caller-supplied refs (`before..after` and `exclude_ref`): once git
        sees `--end-of-options` no further `-`-prefixed *option* can follow
        (a trailing `--not` would itself error), but `^ref`/`A..B` are
        revision syntax, not options, and still parse correctly after it.
        """
        result = subprocess.run(
            [
                self._git_bin,
                "-C",
                repo_path,
                "rev-list",
                "--no-merges",
                "--end-of-options",
                f"{before}..{after}",
                f"^{exclude_ref}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return ()
        return tuple(line for line in result.stdout.splitlines() if line.strip())

    def _branch_names(self, repo_path: str) -> list[str]:
        result = subprocess.run(
            [
                self._git_bin,
                "-C",
                repo_path,
                "for-each-ref",
                "--format=%(refname:short)",
                "--end-of-options",
                "refs/heads/",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return []
        return [line for line in result.stdout.splitlines() if line.strip()]

    def _rev_list(self, repo_path: str, *args: str, ref: str) -> list[str]:
        result = subprocess.run(
            [self._git_bin, "-C", repo_path, "rev-list", *args, "--end-of-options", ref],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return []
        return [line for line in result.stdout.splitlines() if line.strip()]

    def commit_timestamp(self, repo_path: str, ref: str) -> datetime:
        result = subprocess.run(
            [self._git_bin, "-C", repo_path, "show", "-s", "--format=%cI", "--end-of-options", ref],
            capture_output=True,
            text=True,
            check=True,
        )
        return datetime.fromisoformat(result.stdout.strip())

    def _current_branch(self, repo_path: str) -> str:
        result = subprocess.run(
            [self._git_bin, "-C", repo_path, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def _collect_commits(self, repo_path: str, rev_range: str) -> tuple[Commit, ...]:
        result = subprocess.run(
            [
                self._git_bin,
                "-c",
                "core.quotepath=false",
                "-C",
                repo_path,
                "log",
                "--numstat",
                "--shortstat",
                f"--pretty=format:{_PRETTY_FORMAT}",
                "--end-of-options",
                rev_range,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        commits = []
        for record in result.stdout.split(_RECORD_SEP):
            if not record.strip():
                continue
            commit = self._parse_record(record)
            if commit is not None:
                commits.append(commit)
        return tuple(commits)

    def _parse_record(self, record: str) -> Commit | None:
        # 4 field separators (after H, an, s, b) isolate exactly 5 parts: the trailing
        # one is the stat area (numstat/shortstat lines) that follows the body field.
        parts = record.split(_FIELD_SEP, 4)
        if len(parts) < 5:
            return None
        sha, author, subject, body, tail = parts
        body = body.strip()
        changed_files, diffstat = self._parse_tail(tail)
        message = subject if not body else f"{subject}\n\n{body}"
        return Commit(
            sha=sha,
            author=author,
            message=message,
            changed_files=changed_files,
            diffstat=diffstat,
        )

    def _parse_tail(self, tail: str) -> tuple[tuple[str, ...], str]:
        changed_files: list[str] = []
        diffstat = ""
        for line in tail.split("\n"):
            numstat_match = _NUMSTAT_RE.match(line)
            if numstat_match:
                changed_files.append(numstat_match.group(1))
                continue
            if _SHORTSTAT_RE.match(line):
                diffstat = line.strip()
        return tuple(changed_files), diffstat
