from src.commits.models import Commit, CommitContext

_HEADER_TEMPLATE = "Repository: {repo}\nBranch: {branch}\n"

_COMMIT_TEMPLATE = "- {message}\n  Files changed: {changed_files}\n  {diffstat}"

_INSTRUCTION_TEMPLATE = (
    "\n\nWrite concise, human-readable release notes summarizing the changes above, "
    "in {lang}."
)


class PromptBuilder:
    """Renders a CommitContext into a plain-text prompt for an LLM."""

    def build(self, context: CommitContext, lang: str = "ru") -> str:
        header = _HEADER_TEMPLATE.format(repo=context.repo, branch=context.branch)
        commits = "\n".join(self._render_commit(commit) for commit in context.commits)
        instruction = _INSTRUCTION_TEMPLATE.format(lang=lang)
        return f"{header}\n{commits}{instruction}"

    def _render_commit(self, commit: Commit) -> str:
        changed_files = ", ".join(commit.changed_files) if commit.changed_files else "none"
        return _COMMIT_TEMPLATE.format(
            message=commit.message,
            changed_files=changed_files,
            diffstat=commit.diffstat,
        )
