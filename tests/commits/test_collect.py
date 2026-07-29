"""Collect group for `GitCommitCollector.collect`: the honest end-to-end
check that real git output still matches `parse_log`'s expectations, run
against the shared `git_repo` / `commit_at` fixtures in
`tests/commits/conftest.py`.

The suite splits three ways: `test_parse_log.py` drives the pure parse with
no git process, `test_collector.py` covers the collector's other git-backed
queries, and this file checks `collect` end to end against real git output.
"""

import subprocess

import pytest

from src.commits.collector import EMPTY_TREE_SHA, GitCommitCollector
from tests.commits.conftest import _git


@pytest.fixture
def collector() -> GitCommitCollector:
    return GitCommitCollector()


# --- Task 4: record framing, ordering, empty range (`collect` / `_run_log` / `parse_log` end-to-end) ---


def test_should_return_one_commit_per_commit_newest_first_when_the_range_spans_several_commits(
    git_repo, commit_at, collector
):
    first_sha = commit_at(git_repo, "first commit")
    second_sha = commit_at(git_repo, "second commit")
    third_sha = commit_at(git_repo, "third commit")

    ctx = collector.collect(str(git_repo), "HEAD")

    assert tuple(c.sha for c in ctx.commits) == (third_sha, second_sha, first_sha)


def test_should_not_emit_a_phantom_empty_commit_for_the_leading_nul_marker_when_the_range_is_non_empty(
    git_repo, commit_at, collector
):
    commit_at(git_repo, "first commit")
    commit_at(git_repo, "second commit")
    commit_at(git_repo, "third commit")

    ctx = collector.collect(str(git_repo), "HEAD")

    assert len(ctx.commits) == 3


def test_should_return_an_empty_commits_tuple_and_branch_main_without_raising_when_the_range_is_well_formed_but_empty(
    git_repo, commit_at, collector
):
    sha = commit_at(git_repo, "only commit")

    ctx = collector.collect(str(git_repo), f"{sha}..{sha}")

    assert ctx.commits == ()
    assert ctx.branch == "main"


# --- Task 5: changed_files / diffstat extraction on real git output (`_parse_tail`) ---


def test_should_populate_changed_files_with_every_touched_path_and_set_diffstat_to_the_space_stripped_shortstat_line_when_a_commit_touches_several_files(
    git_repo, commit_at, collector
):
    (git_repo / "a.txt").write_text("a\n")
    (git_repo / "b.txt").write_text("b\n")
    _git("add", "-A", cwd=git_repo)
    commit_at(git_repo, "add two files")

    ctx = collector.collect(str(git_repo), "HEAD")

    assert ctx.commits[0].changed_files == ("a.txt", "b.txt")
    assert ctx.commits[0].diffstat == "2 files changed, 2 insertions(+)"


def test_should_return_the_full_untruncated_path_when_a_commit_touches_a_path_well_over_80_characters(
    git_repo, commit_at, collector
):
    long_name = "x" * 100 + ".md"
    assert len(long_name) > 80
    (git_repo / long_name).write_text("content\n")
    _git("add", "-A", cwd=git_repo)
    commit_at(git_repo, "add long path")

    ctx = collector.collect(str(git_repo), "HEAD")

    assert ctx.commits[0].changed_files == (long_name,)
    assert not ctx.commits[0].changed_files[0].startswith("...")


def test_should_include_a_binary_file_in_changed_files_and_report_1_file_changed_when_git_renders_its_numstat_counts_as_dash(
    git_repo, commit_at, collector
):
    (git_repo / "image.bin").write_bytes(bytes([0, 1, 2, 3, 255, 254]))
    _git("add", "-A", cwd=git_repo)
    commit_at(git_repo, "add binary file")

    ctx = collector.collect(str(git_repo), "HEAD")

    assert ctx.commits[0].changed_files == ("image.bin",)
    assert ctx.commits[0].diffstat == "1 file changed, 0 insertions(+), 0 deletions(-)"


def test_should_keep_changed_files_and_diffstat_empty_while_keeping_the_commit_present_when_a_commit_touches_zero_files(
    git_repo, commit_at, collector
):
    commit_at(git_repo, "empty commit")

    ctx = collector.collect(str(git_repo), "HEAD")

    assert len(ctx.commits) == 1
    assert ctx.commits[0].changed_files == ()
    assert ctx.commits[0].diffstat == ""


def test_should_preserve_a_path_containing_spaces_intact(git_repo, commit_at, collector):
    (git_repo / "my notes").mkdir()
    (git_repo / "my notes" / "file one.md").write_text("hi\n")
    _git("add", "-A", cwd=git_repo)
    commit_at(git_repo, "add spaced path")

    ctx = collector.collect(str(git_repo), "HEAD")

    assert ctx.commits[0].changed_files == ("my notes/file one.md",)


# --- Task 6: non-ASCII path, author, and message round-trip (`_run_log` / `_parse_record`) ---


def test_should_return_a_non_ascii_path_literally_rather_than_c_quoted_with_octal_escapes(
    git_repo, commit_at, collector
):
    (git_repo / "документ.md").write_text("содержимое\n")
    _git("add", "-A", cwd=git_repo)
    commit_at(git_repo, "add non-ascii path")

    ctx = collector.collect(str(git_repo), "HEAD")

    assert ctx.commits[0].changed_files == ("документ.md",)


def test_should_preserve_a_non_ascii_author_name_exactly_as_an_emits_it(git_repo, commit_at, collector):
    commit_at(git_repo, "first commit")
    _git(
        "-c", "user.name=Ирина Петрова",
        "-c", "user.email=irina@test.invalid",
        "commit", "-q", "--allow-empty", "-m", "non-ascii author commit",
        cwd=git_repo,
    )

    ctx = collector.collect(str(git_repo), "HEAD")

    assert ctx.commits[0].author == "Ирина Петрова"


def test_should_preserve_a_non_ascii_commit_message_exactly(git_repo, commit_at, collector):
    commit_at(git_repo, "first commit")
    _git(
        "-c", "user.name=herald-test",
        "-c", "user.email=herald@test.invalid",
        "commit", "-q", "--allow-empty", "-m", "Исправлена ошибка в парсере",
        cwd=git_repo,
    )

    ctx = collector.collect(str(git_repo), "HEAD")

    assert ctx.commits[0].message == "Исправлена ошибка в парсере"


# --- Task 7: range semantics (`collect`) ---


def test_should_return_the_whole_reachable_history_when_before_is_the_empty_tree_sha_sentinel(
    git_repo, commit_at, collector
):
    first_sha = commit_at(git_repo, "first commit")
    second_sha = commit_at(git_repo, "second commit")

    ctx = collector.collect(str(git_repo), f"{EMPTY_TREE_SHA}..HEAD")

    assert tuple(c.sha for c in ctx.commits) == (second_sha, first_sha)


def test_should_raise_calledprocesserror_when_the_revision_range_is_unknown_or_malformed(
    git_repo, commit_at, collector
):
    commit_at(git_repo, "only commit")

    with pytest.raises(subprocess.CalledProcessError):
        collector.collect(str(git_repo), "does-not-exist..HEAD")


# --- Task 8: CommitContext shape and branch label (`collect` / `_current_branch`) ---


def test_should_set_repo_to_the_given_repo_path_verbatim_and_branch_to_the_checked_out_branch(
    git_repo, commit_at, collector
):
    commit_at(git_repo, "only commit")

    ctx = collector.collect(str(git_repo), "HEAD")

    assert ctx.repo == str(git_repo)
    assert ctx.branch == "main"


def test_should_report_branch_as_head_when_the_repo_is_in_detached_head_state(git_repo, commit_at, collector):
    sha = commit_at(git_repo, "only commit")
    _git("checkout", "-q", sha, cwd=git_repo)

    ctx = collector.collect(str(git_repo), "HEAD")

    assert ctx.branch == "HEAD"
