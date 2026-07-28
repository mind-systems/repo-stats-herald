"""Parse group for `GitCommitCollector.parse_log`: pure string-in /
`CommitContext`-out cases, no git process and no fixture repo. Each case
builds the raw log text as it would arrive from `_run_log` — records
joined by `\\x00` fields (sha, author, subject, body, tail), with the
leading `\\x00` marker `_PRETTY_FORMAT` prefixes to every record.

The three-file split (`test_collector.py` / `test_parse_log.py` /
`test_collect.py`) is documented in
`.ai-factory/specs/77-commit-collector-parse-test-plan.md`.
"""

import pytest

from src.commits.collector import GitCommitCollector


@pytest.fixture
def collector() -> GitCommitCollector:
    return GitCommitCollector()


def _log_text(*records: tuple[str, str, str, str, str]) -> str:
    """Build raw `git log` text the way `_run_log` emits it: a leading
    empty field (the first record's `%x00` marker, produced by
    `log_text.split("\\x00")`) followed by five NUL-joined fields per
    record — sha, author, subject, body, tail."""
    fields = [""]
    for record in records:
        fields.extend(record)
    return "\x00".join(fields)


# Captured once from real `git log --numstat --shortstat
# --pretty=format:'%x00%H%x00%an%x00%s%x00%b%x00'` output against a commit
# that renames a file inside a directory with a shared prefix, so the
# assertion pins git's actual brace-compressed emission rather than a
# hand-guessed "old => new" form.
_RENAME_RECORD = (
    "\x0041bffbfcbc8b5bc8d282e9ae9c6c932af73598c4\x00herald-test\x00"
    "rename spec doc to behavior\x00\x00\n"
    "0\t0\tdocs/{spec => behavior}/a.md\n"
    " 1 file changed, 0 insertions(+), 0 deletions(-)\n"
)

# Captured once from a real range spanning four commits: a trunk commit,
# a --no-ff merge of a feature branch, the feature commit itself, and the
# trunk commit the feature branch forked from — newest-first, exactly as
# `git log` emits a range. The merge record's tail is empty because
# `git log --numstat` reports no per-file stats for a merge without `-m`.
_MERGE_RANGE_LOG = (
    "\x001b040d12c29b9e6bf36d87e8028daeb13fe50e85\x00herald-test\x00"
    "trunk progress after merge\x00\x00\n"
    "\x00a51b2baab09ece4d0dd59673de45ccc525c7a721\x00herald-test\x00"
    "merge feature into main\x00\x00\n"
    "\x00d477648899f55fe68d86febce25a24321a79c948\x00herald-test\x00"
    "feature work\x00\x00\n"
    "\x004715b00e19e3638e5aefadf97b0db2f2df5154f5\x00herald-test\x00"
    "trunk progress before merge\x00\x00"
)

# Captured once from a real commit that adds 250 files in one shot, so the
# full-count assertion below pins actual git output rather than a
# hand-guessed shape for a large stat block.
_BULK_RECORD_TAIL = (
    "\x00118fc5ee8cc8c597712b7c6e0954429b3483cdc0\x00herald-test\x00add 250 files\x00\x00\n"
    "1\t0\tbulk/file_001.txt\n"
    "1\t0\tbulk/file_002.txt\n"
    "1\t0\tbulk/file_003.txt\n"
    "1\t0\tbulk/file_004.txt\n"
    "1\t0\tbulk/file_005.txt\n"
    "1\t0\tbulk/file_006.txt\n"
    "1\t0\tbulk/file_007.txt\n"
    "1\t0\tbulk/file_008.txt\n"
    "1\t0\tbulk/file_009.txt\n"
    "1\t0\tbulk/file_010.txt\n"
    "1\t0\tbulk/file_011.txt\n"
    "1\t0\tbulk/file_012.txt\n"
    "1\t0\tbulk/file_013.txt\n"
    "1\t0\tbulk/file_014.txt\n"
    "1\t0\tbulk/file_015.txt\n"
    "1\t0\tbulk/file_016.txt\n"
    "1\t0\tbulk/file_017.txt\n"
    "1\t0\tbulk/file_018.txt\n"
    "1\t0\tbulk/file_019.txt\n"
    "1\t0\tbulk/file_020.txt\n"
    "1\t0\tbulk/file_021.txt\n"
    "1\t0\tbulk/file_022.txt\n"
    "1\t0\tbulk/file_023.txt\n"
    "1\t0\tbulk/file_024.txt\n"
    "1\t0\tbulk/file_025.txt\n"
    "1\t0\tbulk/file_026.txt\n"
    "1\t0\tbulk/file_027.txt\n"
    "1\t0\tbulk/file_028.txt\n"
    "1\t0\tbulk/file_029.txt\n"
    "1\t0\tbulk/file_030.txt\n"
    "1\t0\tbulk/file_031.txt\n"
    "1\t0\tbulk/file_032.txt\n"
    "1\t0\tbulk/file_033.txt\n"
    "1\t0\tbulk/file_034.txt\n"
    "1\t0\tbulk/file_035.txt\n"
    "1\t0\tbulk/file_036.txt\n"
    "1\t0\tbulk/file_037.txt\n"
    "1\t0\tbulk/file_038.txt\n"
    "1\t0\tbulk/file_039.txt\n"
    "1\t0\tbulk/file_040.txt\n"
    "1\t0\tbulk/file_041.txt\n"
    "1\t0\tbulk/file_042.txt\n"
    "1\t0\tbulk/file_043.txt\n"
    "1\t0\tbulk/file_044.txt\n"
    "1\t0\tbulk/file_045.txt\n"
    "1\t0\tbulk/file_046.txt\n"
    "1\t0\tbulk/file_047.txt\n"
    "1\t0\tbulk/file_048.txt\n"
    "1\t0\tbulk/file_049.txt\n"
    "1\t0\tbulk/file_050.txt\n"
    "1\t0\tbulk/file_051.txt\n"
    "1\t0\tbulk/file_052.txt\n"
    "1\t0\tbulk/file_053.txt\n"
    "1\t0\tbulk/file_054.txt\n"
    "1\t0\tbulk/file_055.txt\n"
    "1\t0\tbulk/file_056.txt\n"
    "1\t0\tbulk/file_057.txt\n"
    "1\t0\tbulk/file_058.txt\n"
    "1\t0\tbulk/file_059.txt\n"
    "1\t0\tbulk/file_060.txt\n"
    "1\t0\tbulk/file_061.txt\n"
    "1\t0\tbulk/file_062.txt\n"
    "1\t0\tbulk/file_063.txt\n"
    "1\t0\tbulk/file_064.txt\n"
    "1\t0\tbulk/file_065.txt\n"
    "1\t0\tbulk/file_066.txt\n"
    "1\t0\tbulk/file_067.txt\n"
    "1\t0\tbulk/file_068.txt\n"
    "1\t0\tbulk/file_069.txt\n"
    "1\t0\tbulk/file_070.txt\n"
    "1\t0\tbulk/file_071.txt\n"
    "1\t0\tbulk/file_072.txt\n"
    "1\t0\tbulk/file_073.txt\n"
    "1\t0\tbulk/file_074.txt\n"
    "1\t0\tbulk/file_075.txt\n"
    "1\t0\tbulk/file_076.txt\n"
    "1\t0\tbulk/file_077.txt\n"
    "1\t0\tbulk/file_078.txt\n"
    "1\t0\tbulk/file_079.txt\n"
    "1\t0\tbulk/file_080.txt\n"
    "1\t0\tbulk/file_081.txt\n"
    "1\t0\tbulk/file_082.txt\n"
    "1\t0\tbulk/file_083.txt\n"
    "1\t0\tbulk/file_084.txt\n"
    "1\t0\tbulk/file_085.txt\n"
    "1\t0\tbulk/file_086.txt\n"
    "1\t0\tbulk/file_087.txt\n"
    "1\t0\tbulk/file_088.txt\n"
    "1\t0\tbulk/file_089.txt\n"
    "1\t0\tbulk/file_090.txt\n"
    "1\t0\tbulk/file_091.txt\n"
    "1\t0\tbulk/file_092.txt\n"
    "1\t0\tbulk/file_093.txt\n"
    "1\t0\tbulk/file_094.txt\n"
    "1\t0\tbulk/file_095.txt\n"
    "1\t0\tbulk/file_096.txt\n"
    "1\t0\tbulk/file_097.txt\n"
    "1\t0\tbulk/file_098.txt\n"
    "1\t0\tbulk/file_099.txt\n"
    "1\t0\tbulk/file_100.txt\n"
    "1\t0\tbulk/file_101.txt\n"
    "1\t0\tbulk/file_102.txt\n"
    "1\t0\tbulk/file_103.txt\n"
    "1\t0\tbulk/file_104.txt\n"
    "1\t0\tbulk/file_105.txt\n"
    "1\t0\tbulk/file_106.txt\n"
    "1\t0\tbulk/file_107.txt\n"
    "1\t0\tbulk/file_108.txt\n"
    "1\t0\tbulk/file_109.txt\n"
    "1\t0\tbulk/file_110.txt\n"
    "1\t0\tbulk/file_111.txt\n"
    "1\t0\tbulk/file_112.txt\n"
    "1\t0\tbulk/file_113.txt\n"
    "1\t0\tbulk/file_114.txt\n"
    "1\t0\tbulk/file_115.txt\n"
    "1\t0\tbulk/file_116.txt\n"
    "1\t0\tbulk/file_117.txt\n"
    "1\t0\tbulk/file_118.txt\n"
    "1\t0\tbulk/file_119.txt\n"
    "1\t0\tbulk/file_120.txt\n"
    "1\t0\tbulk/file_121.txt\n"
    "1\t0\tbulk/file_122.txt\n"
    "1\t0\tbulk/file_123.txt\n"
    "1\t0\tbulk/file_124.txt\n"
    "1\t0\tbulk/file_125.txt\n"
    "1\t0\tbulk/file_126.txt\n"
    "1\t0\tbulk/file_127.txt\n"
    "1\t0\tbulk/file_128.txt\n"
    "1\t0\tbulk/file_129.txt\n"
    "1\t0\tbulk/file_130.txt\n"
    "1\t0\tbulk/file_131.txt\n"
    "1\t0\tbulk/file_132.txt\n"
    "1\t0\tbulk/file_133.txt\n"
    "1\t0\tbulk/file_134.txt\n"
    "1\t0\tbulk/file_135.txt\n"
    "1\t0\tbulk/file_136.txt\n"
    "1\t0\tbulk/file_137.txt\n"
    "1\t0\tbulk/file_138.txt\n"
    "1\t0\tbulk/file_139.txt\n"
    "1\t0\tbulk/file_140.txt\n"
    "1\t0\tbulk/file_141.txt\n"
    "1\t0\tbulk/file_142.txt\n"
    "1\t0\tbulk/file_143.txt\n"
    "1\t0\tbulk/file_144.txt\n"
    "1\t0\tbulk/file_145.txt\n"
    "1\t0\tbulk/file_146.txt\n"
    "1\t0\tbulk/file_147.txt\n"
    "1\t0\tbulk/file_148.txt\n"
    "1\t0\tbulk/file_149.txt\n"
    "1\t0\tbulk/file_150.txt\n"
    "1\t0\tbulk/file_151.txt\n"
    "1\t0\tbulk/file_152.txt\n"
    "1\t0\tbulk/file_153.txt\n"
    "1\t0\tbulk/file_154.txt\n"
    "1\t0\tbulk/file_155.txt\n"
    "1\t0\tbulk/file_156.txt\n"
    "1\t0\tbulk/file_157.txt\n"
    "1\t0\tbulk/file_158.txt\n"
    "1\t0\tbulk/file_159.txt\n"
    "1\t0\tbulk/file_160.txt\n"
    "1\t0\tbulk/file_161.txt\n"
    "1\t0\tbulk/file_162.txt\n"
    "1\t0\tbulk/file_163.txt\n"
    "1\t0\tbulk/file_164.txt\n"
    "1\t0\tbulk/file_165.txt\n"
    "1\t0\tbulk/file_166.txt\n"
    "1\t0\tbulk/file_167.txt\n"
    "1\t0\tbulk/file_168.txt\n"
    "1\t0\tbulk/file_169.txt\n"
    "1\t0\tbulk/file_170.txt\n"
    "1\t0\tbulk/file_171.txt\n"
    "1\t0\tbulk/file_172.txt\n"
    "1\t0\tbulk/file_173.txt\n"
    "1\t0\tbulk/file_174.txt\n"
    "1\t0\tbulk/file_175.txt\n"
    "1\t0\tbulk/file_176.txt\n"
    "1\t0\tbulk/file_177.txt\n"
    "1\t0\tbulk/file_178.txt\n"
    "1\t0\tbulk/file_179.txt\n"
    "1\t0\tbulk/file_180.txt\n"
    "1\t0\tbulk/file_181.txt\n"
    "1\t0\tbulk/file_182.txt\n"
    "1\t0\tbulk/file_183.txt\n"
    "1\t0\tbulk/file_184.txt\n"
    "1\t0\tbulk/file_185.txt\n"
    "1\t0\tbulk/file_186.txt\n"
    "1\t0\tbulk/file_187.txt\n"
    "1\t0\tbulk/file_188.txt\n"
    "1\t0\tbulk/file_189.txt\n"
    "1\t0\tbulk/file_190.txt\n"
    "1\t0\tbulk/file_191.txt\n"
    "1\t0\tbulk/file_192.txt\n"
    "1\t0\tbulk/file_193.txt\n"
    "1\t0\tbulk/file_194.txt\n"
    "1\t0\tbulk/file_195.txt\n"
    "1\t0\tbulk/file_196.txt\n"
    "1\t0\tbulk/file_197.txt\n"
    "1\t0\tbulk/file_198.txt\n"
    "1\t0\tbulk/file_199.txt\n"
    "1\t0\tbulk/file_200.txt\n"
    "1\t0\tbulk/file_201.txt\n"
    "1\t0\tbulk/file_202.txt\n"
    "1\t0\tbulk/file_203.txt\n"
    "1\t0\tbulk/file_204.txt\n"
    "1\t0\tbulk/file_205.txt\n"
    "1\t0\tbulk/file_206.txt\n"
    "1\t0\tbulk/file_207.txt\n"
    "1\t0\tbulk/file_208.txt\n"
    "1\t0\tbulk/file_209.txt\n"
    "1\t0\tbulk/file_210.txt\n"
    "1\t0\tbulk/file_211.txt\n"
    "1\t0\tbulk/file_212.txt\n"
    "1\t0\tbulk/file_213.txt\n"
    "1\t0\tbulk/file_214.txt\n"
    "1\t0\tbulk/file_215.txt\n"
    "1\t0\tbulk/file_216.txt\n"
    "1\t0\tbulk/file_217.txt\n"
    "1\t0\tbulk/file_218.txt\n"
    "1\t0\tbulk/file_219.txt\n"
    "1\t0\tbulk/file_220.txt\n"
    "1\t0\tbulk/file_221.txt\n"
    "1\t0\tbulk/file_222.txt\n"
    "1\t0\tbulk/file_223.txt\n"
    "1\t0\tbulk/file_224.txt\n"
    "1\t0\tbulk/file_225.txt\n"
    "1\t0\tbulk/file_226.txt\n"
    "1\t0\tbulk/file_227.txt\n"
    "1\t0\tbulk/file_228.txt\n"
    "1\t0\tbulk/file_229.txt\n"
    "1\t0\tbulk/file_230.txt\n"
    "1\t0\tbulk/file_231.txt\n"
    "1\t0\tbulk/file_232.txt\n"
    "1\t0\tbulk/file_233.txt\n"
    "1\t0\tbulk/file_234.txt\n"
    "1\t0\tbulk/file_235.txt\n"
    "1\t0\tbulk/file_236.txt\n"
    "1\t0\tbulk/file_237.txt\n"
    "1\t0\tbulk/file_238.txt\n"
    "1\t0\tbulk/file_239.txt\n"
    "1\t0\tbulk/file_240.txt\n"
    "1\t0\tbulk/file_241.txt\n"
    "1\t0\tbulk/file_242.txt\n"
    "1\t0\tbulk/file_243.txt\n"
    "1\t0\tbulk/file_244.txt\n"
    "1\t0\tbulk/file_245.txt\n"
    "1\t0\tbulk/file_246.txt\n"
    "1\t0\tbulk/file_247.txt\n"
    "1\t0\tbulk/file_248.txt\n"
    "1\t0\tbulk/file_249.txt\n"
    "1\t0\tbulk/file_250.txt\n"
    " 250 files changed, 250 insertions(+)\n"
)


# --- Task 1: subject/body joining (`_parse_record`) ---


def test_should_join_subject_and_body_as_subject_blank_body_when_a_record_has_a_multi_line_body(collector):
    text = _log_text(("sha1", "Jane Doe", "Fix the bug", "Line one\nLine two", ""))

    ctx = collector.parse_log(text, repo="r", branch="main")

    assert ctx.commits[0].message == "Fix the bug\n\nLine one\nLine two"


def test_should_strip_trailing_whitespace_from_the_body_so_no_blank_tail_survives_in_the_message(collector):
    text = _log_text(("sha1", "Jane Doe", "Fix the bug", "Body line\n\n\n", ""))

    ctx = collector.parse_log(text, repo="r", branch="main")

    assert ctx.commits[0].message == "Fix the bug\n\nBody line"


def test_should_set_message_to_the_subject_alone_when_a_records_body_field_is_empty(collector):
    text = _log_text(("sha1", "Jane Doe", "Fix the bug", "", ""))

    ctx = collector.parse_log(text, repo="r", branch="main")

    assert ctx.commits[0].message == "Fix the bug"


# --- Task 2: field-isolation injection guards (`_parse_record` NUL isolation + `_parse_tail`) ---


def test_should_keep_changed_files_to_the_real_numstat_paths_when_a_body_field_contains_a_line_shaped_like_a_numstat_line(
    collector,
):
    body = "See the fix here.\n12\t3\tfake/injected.py\nMore notes."
    tail = "\n4\t1\treal/path.py\n 1 file changed, 4 insertions(+), 1 deletion(-)\n"
    text = _log_text(("sha1", "Jane Doe", "Fix real thing", body, tail))

    ctx = collector.parse_log(text, repo="r", branch="main")

    assert ctx.commits[0].changed_files == ("real/path.py",)


def test_should_not_overwrite_diffstat_when_a_body_field_contains_a_line_shaped_like_a_shortstat_summary(collector):
    body = "Reviewed-by note.\n 99 files changed, 999 insertions(+), 999 deletions(-)\nend."
    tail = "\n2\t1\treal/path.py\n1\t0\tother/path.py\n 2 files changed, 3 insertions(+), 1 deletion(-)\n"
    text = _log_text(("sha1", "Jane Doe", "Fix real thing", body, tail))

    ctx = collector.parse_log(text, repo="r", branch="main")

    assert ctx.commits[0].diffstat == "2 files changed, 3 insertions(+), 1 deletion(-)"


# --- Task 3: numstat/shortstat extraction over real captured blocks (`_parse_tail`) ---


def test_should_keep_gits_brace_compressed_rename_path_verbatim_when_a_captured_record_renames_a_file_inside_a_directory(
    collector,
):
    ctx = collector.parse_log(_RENAME_RECORD, repo="r", branch="main")

    assert ctx.commits[0].changed_files == ("docs/{spec => behavior}/a.md",)


def test_should_return_empty_changed_files_and_empty_diffstat_for_a_merge_record_while_the_sibling_non_merge_records_in_the_same_log_still_parse(
    collector,
):
    ctx = collector.parse_log(_MERGE_RANGE_LOG, repo="r", branch="main")

    assert [c.message for c in ctx.commits] == [
        "trunk progress after merge",
        "merge feature into main",
        "feature work",
        "trunk progress before merge",
    ]

    merge_commit = ctx.commits[1]
    assert merge_commit.changed_files == ()
    assert merge_commit.diffstat == ""

    assert ctx.commits[0].sha == "1b040d12c29b9e6bf36d87e8028daeb13fe50e85"
    assert ctx.commits[2].sha == "d477648899f55fe68d86febce25a24321a79c948"
    assert ctx.commits[3].sha == "4715b00e19e3638e5aefadf97b0db2f2df5154f5"


def test_should_capture_every_path_without_truncation_or_dropping_when_a_captured_records_stat_block_lists_250_files(
    collector,
):
    ctx = collector.parse_log(_BULK_RECORD_TAIL, repo="r", branch="main")

    assert len(ctx.commits) == 1
    changed_files = ctx.commits[0].changed_files
    assert len(changed_files) == 250
    assert changed_files[0] == "bulk/file_001.txt"
    assert changed_files[-1] == "bulk/file_250.txt"
    assert ctx.commits[0].diffstat == "250 files changed, 250 insertions(+)"
