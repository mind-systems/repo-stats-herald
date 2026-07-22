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
