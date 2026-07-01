# commits/ Feature — Domain Models + Git Collector

**Date:** 2026-07-01
**Source:** conversation context

## Key Findings

- Nothing represents a commit or a commit range, and there is no way to read real history to feed the summarizer.
- This task creates the `commits/` feature module: immutable domain value objects (`Commit`, `CommitContext`) and a `GitCommitCollector` that reads a revision range from a **local** git repo. No GitHub API yet — that comes with the webhook milestone.

## Details

### Current state
No models, no collector. The spike needs real input; the cheapest real source is local `git log` against any repo on disk (including this one).

### Target
- `src/commits/__init__.py`
- `src/commits/models.py` — immutable value objects (frozen dataclasses or pydantic `frozen=True`):
  ```python
  @dataclass(frozen=True, slots=True)
  class Commit:
      sha: str
      author: str
      message: str
      changed_files: tuple[str, ...]
      diffstat: str            # e.g. "3 files changed, 40 insertions(+), 5 deletions(-)"

  @dataclass(frozen=True, slots=True)
  class CommitContext:
      repo: str                # repo name or path label
      branch: str
      commits: tuple[Commit, ...]
  ```
- `src/commits/collector.py`:
  ```python
  class GitCommitCollector:
      def collect(self, repo_path: str, rev_range: str) -> CommitContext: ...
  ```
  Implementation shells out to git (read-only), one call per concern, parsed into the models:
  - `git -C <repo> log <range> --pretty=%H%x00%an%x00%s%x00%b` for sha/author/subject/body
  - `git -C <repo> show --stat --oneline <sha>` (or `git log --stat`) for changed files + diffstat
  - current branch via `git -C <repo> rev-parse --abbrev-ref HEAD`

### Architecture notes
Feature owns its own models — no root-level `models/` dump. `GitCommitCollector` is a plain class (constructor may take nothing, or a `git` binary path for testability). It returns domain objects, never raw strings, so the summarization feature depends on the model, not on git output format. This is the seam that later lets a `GitHubCommitCollector` replace it without touching summarization.

### Guards
- Read-only git only — never mutate the target repo, never network.
- Parse defensively: empty ranges, merge commits, commits with empty body must not crash.
- Use a NUL (`%x00`) field separator, not spaces/newlines, so commit messages with arbitrary text parse cleanly.

### Verify
- `GitCommitCollector().collect(".", "HEAD~3..HEAD")` against this repo returns a `CommitContext` with 3 populated `Commit`s (sha, author, message, changed_files, diffstat all non-empty for real commits).

## Open Questions

- Whether to keep a `Collector` abstract base now or introduce it when the GitHub collector actually lands. Leaning: introduce the ABC only when the second implementation arrives (avoid speculative abstraction).
