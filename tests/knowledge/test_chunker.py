from src.knowledge.chunker import MAX_CHUNK_CHARS, chunk_markdown

MULTI_SECTION_DOC = """## Section One
This is the first section body with a distinctive line ONE-BODY-MARKER.

## Section Two
This is the second section body with a distinctive line TWO-BODY-MARKER.

## Section Three
This is the third section body with a distinctive line THREE-BODY-MARKER.
"""

_SENTENCE = (
    "Herald indexes documentation chunks that stay under a size limit so retrieval keeps its point."
)


def _build_oversized_section() -> str:
    """A single `##` section, built from complete-sentence sub-heading
    paragraphs, sized just over `MAX_CHUNK_CHARS` — large enough to force a
    split, without padding far past the threshold."""
    lines = ["## Oversized Section"]
    sub_heading_index = 0
    while len("\n".join(lines)) <= MAX_CHUNK_CHARS:
        sub_heading_index += 1
        lines.append("")
        lines.append(f"### Sub-heading {sub_heading_index}")
        lines.append("")
        lines.append(" ".join([_SENTENCE] * 3))
    return "\n".join(lines)


OVERSIZED_SECTION = _build_oversized_section()


def _ends_at_boundary(chunk: str) -> bool:
    stripped = chunk.strip()
    assert stripped, "a produced chunk must not be blank"
    last_line = stripped.splitlines()[-1].strip()
    return last_line.startswith("#") or stripped.endswith((".", "!", "?"))


def test_chunk_markdown_splits_into_one_chunk_per_heading_section() -> None:
    chunks = chunk_markdown(MULTI_SECTION_DOC)

    assert len(chunks) == 3
    assert "## Section One" in chunks[0]
    assert "ONE-BODY-MARKER" in chunks[0]
    assert "## Section Two" in chunks[1]
    assert "TWO-BODY-MARKER" in chunks[1]
    assert "## Section Three" in chunks[2]
    assert "THREE-BODY-MARKER" in chunks[2]


def test_chunk_markdown_splits_oversized_section_without_cutting_mid_sentence() -> None:
    assert len(OVERSIZED_SECTION) > MAX_CHUNK_CHARS

    chunks = chunk_markdown(OVERSIZED_SECTION)

    assert len(chunks) > 1
    for chunk in chunks:
        assert _ends_at_boundary(chunk)
    # Strengthened: the split happens exactly on the nested sub-headings, in order.
    assert chunks[0].startswith("## Oversized Section")
    for index, chunk in enumerate(chunks[1:], start=1):
        assert chunk.startswith(f"### Sub-heading {index}")


# --- Phase 1: section boundary detection (the core contract) ---------------


def test_chunk_markdown_keeps_heading_and_body_together_under_the_limit() -> None:
    chunks = chunk_markdown(MULTI_SECTION_DOC)

    assert chunks[0].startswith("## Section One")


def test_chunk_markdown_treats_preamble_as_its_own_leading_chunk() -> None:
    doc = "Preamble text before any heading.\n\n## Section One\nbody\n"

    chunks = chunk_markdown(doc)

    assert len(chunks) == 2
    assert chunks[0] == "Preamble text before any heading.\n\n"
    assert chunks[1].startswith("## Section One")


def test_chunk_markdown_returns_whole_document_as_one_chunk_when_no_headings() -> None:
    doc = "Just a plain paragraph with no headings at all."

    chunks = chunk_markdown(doc)

    assert chunks == [doc]


def test_chunk_markdown_emits_one_chunk_for_a_top_heading_with_sub_headings_under_the_limit() -> (
    None
):
    # Non-obvious: min_level is 1 (the shallowest heading present), so the
    # single split start is at index 0 — the `##` sub-headings do NOT start
    # new chunks even though they are real headings.
    doc = "# Title\n## Sub A\nbody a\n## Sub B\nbody b\n"

    chunks = chunk_markdown(doc)

    assert chunks == [doc]


def test_chunk_markdown_splits_at_the_shallowest_level_present_when_it_is_not_h2() -> None:
    doc = "### Top\nbody\n### Second\nbody2\n"

    chunks = chunk_markdown(doc)

    assert len(chunks) == 2
    assert chunks[0] == "### Top\nbody\n"
    assert chunks[1] == "### Second\nbody2\n"


def test_chunk_markdown_keeps_a_deeper_heading_inside_its_parent_chunk() -> None:
    doc = "## A\nbodyA\n### A1\nbodyA1\n## B\nbodyB\n"

    chunks = chunk_markdown(doc)

    assert len(chunks) == 2
    assert chunks[0] == "## A\nbodyA\n### A1\nbodyA1\n"
    assert chunks[1] == "## B\nbodyB\n"


# --- Phase 1: `_HEADING_RE` — what counts as an ATX heading -----------------


def test_chunk_markdown_does_not_treat_a_hash_with_no_space_after_it_as_a_heading() -> None:
    doc = "#hashtag\nbody\n"

    assert chunk_markdown(doc) == [doc]


def test_chunk_markdown_does_not_treat_a_bare_hash_line_as_a_heading() -> None:
    doc = "#\nbody\n"

    assert chunk_markdown(doc) == [doc]


def test_chunk_markdown_does_not_treat_seven_or_more_hashes_as_a_heading() -> None:
    doc = "####### Not a heading\nbody\n"

    assert chunk_markdown(doc) == [doc]


def test_chunk_markdown_does_not_treat_a_hash_run_followed_only_by_whitespace_as_a_heading() -> (
    None
):
    doc = "#   \nbody\n"

    assert chunk_markdown(doc) == [doc]


def test_chunk_markdown_does_not_treat_a_setext_underline_as_a_heading() -> None:
    # Deliberate current limitation: the implementation is ATX-only, so a
    # setext-authored document (`===`/`---` underline) is never section-split.
    doc = "Title\n=====\nbody\n"

    assert chunk_markdown(doc) == [doc]


# --- Phase 2: empty and degenerate input ------------------------------------


def test_chunk_markdown_returns_empty_list_for_empty_string() -> None:
    assert chunk_markdown("") == []


def test_chunk_markdown_returns_empty_list_for_whitespace_only_input() -> None:
    assert chunk_markdown("   \n\n  ") == []


def test_chunk_markdown_keeps_a_heading_with_an_empty_body_as_its_own_chunk() -> None:
    doc = "## A\n## B\n"

    chunks = chunk_markdown(doc)

    assert chunks == ["## A\n", "## B\n"]


def test_chunk_markdown_drops_a_whitespace_only_piece_rather_than_emit_a_blank_chunk() -> None:
    # The only piece that can ever be pure whitespace is the leading preamble
    # piece (every other piece opens on a non-blank heading line); the
    # `piece.strip()` filter drops it instead of yielding a blank chunk.
    doc = "   \n\n## A\nbody\n"

    chunks = chunk_markdown(doc)

    assert chunks == ["## A\nbody\n"]


# --- Phase 3: `_ensure_size` — the exact size boundary ----------------------


def test_chunk_markdown_keeps_a_section_exactly_at_the_limit_as_one_chunk() -> None:
    prefix = "## Sec\n"
    section = prefix + "a" * (MAX_CHUNK_CHARS - len(prefix))
    assert len(section) == MAX_CHUNK_CHARS

    chunks = chunk_markdown(section)

    assert chunks == [section]


def test_chunk_markdown_splits_a_section_one_char_over_the_limit_when_splittable() -> None:
    head = "## Sec\n"
    sub = "### Sub\n"
    body_len = MAX_CHUNK_CHARS + 1 - len(head) - len(sub)
    section = head + sub + "a" * body_len
    assert len(section) == MAX_CHUNK_CHARS + 1

    chunks = chunk_markdown(section)

    assert len(chunks) == 2
    assert chunks[0] == head
    assert chunks[1].startswith(sub)


# --- Phase 3: `_ensure_size` — oversized split on sub-headings --------------


def test_chunk_markdown_splits_oversized_section_keeping_parent_heading_only_on_leading_piece() -> (
    None
):
    sentence = (
        "Herald indexes documentation chunks that stay under a size limit so retrieval keeps its point."
    )
    lines = ["## Parent", "", "Intro paragraph for the parent section."]
    for index in range(4):
        lines.append("")
        lines.append(f"### S{index}")
        lines.append("")
        lines.append(" ".join([sentence] * 6))
    section = "\n".join(lines) + "\n"
    assert len(section) > MAX_CHUNK_CHARS

    chunks = chunk_markdown(section)

    # Deliberate current behaviour: sub-chunks lose the parent heading — only
    # the leading piece carries "## Parent".
    assert len(chunks) == 5
    assert chunks[0].startswith("## Parent")
    assert "### S" not in chunks[0]
    for index, chunk in enumerate(chunks[1:]):
        assert chunk.startswith(f"### S{index}")


def test_chunk_markdown_recurses_when_a_sub_heading_piece_is_itself_oversized() -> None:
    sentence = (
        "Herald indexes documentation chunks that stay under a size limit so retrieval keeps its point."
    )
    paragraph = " ".join([sentence] * 9)
    huge_body = "\n\n".join([paragraph, paragraph, paragraph])
    section = "## Parent\n\nintro\n\n### Huge\n\n" + huge_body + "\n"
    assert len(section) > MAX_CHUNK_CHARS
    assert len(f"### Huge\n\n{huge_body}") > MAX_CHUNK_CHARS

    chunks = chunk_markdown(section)

    # The oversized "### Huge" piece recurses into `_ensure_size`, finds no
    # further sub-headings and falls through to the paragraph splitter —
    # producing a continuation chunk that carries no heading at all.
    assert len(chunks) == 3
    assert chunks[0].startswith("## Parent")
    assert chunks[1].startswith("### Huge")
    assert not chunks[2].startswith("#")


# --- Phase 4: `_split_by_paragraphs` — paragraph grouping -------------------


def _make_paragraph(length: int, marker: str) -> str:
    word = f"{marker}word "
    return (word * (length // len(word) + 1))[:length]


def test_chunk_markdown_groups_whole_paragraphs_up_to_the_limit() -> None:
    para_len = MAX_CHUNK_CHARS // 2 - 100
    p1 = _make_paragraph(para_len, "AAA")
    p2 = _make_paragraph(para_len, "BBB")
    p3 = _make_paragraph(para_len, "CCC")
    section = "## X\n\n" + p1 + "\n\n" + p2 + "\n\n" + p3 + "\n"
    assert len(section) > MAX_CHUNK_CHARS

    chunks = chunk_markdown(section)

    assert len(chunks) == 2
    assert "AAA" in chunks[0] and "BBB" in chunks[0] and "CCC" not in chunks[0]
    assert "CCC" in chunks[1] and "AAA" not in chunks[1] and "BBB" not in chunks[1]


def test_chunk_markdown_never_cuts_inside_a_paragraph_when_grouping() -> None:
    para_len = MAX_CHUNK_CHARS // 2 - 100
    paragraphs = [_make_paragraph(para_len, marker) for marker in ("AAA", "BBB", "CCC")]
    section = "## X\n\n" + "\n\n".join(paragraphs) + "\n"

    chunks = chunk_markdown(section)

    # Every emitted chunk (after stripping the heading, if present) is a
    # contiguous slice of whole source paragraphs, never a fragment.
    for chunk in chunks:
        stripped = chunk.strip()
        assert stripped
        body = stripped.removeprefix("## X").strip()
        if not body:
            continue
        pieces = [p.strip() for p in body.split("\n\n") if p.strip()]
        for piece in pieces:
            assert piece in paragraphs


def test_chunk_markdown_keeps_a_single_over_limit_paragraph_intact() -> None:
    # Deliberate current behaviour: cutting mid-paragraph would violate the
    # "never mid-sentence" rule, so a lone oversized paragraph is kept whole
    # even though the resulting chunk exceeds MAX_CHUNK_CHARS.
    section = "## X\n" + "a" * (MAX_CHUNK_CHARS + 500)

    chunks = chunk_markdown(section)

    assert len(chunks) == 1
    assert len(chunks[0]) > MAX_CHUNK_CHARS


def test_chunk_markdown_splits_oversized_section_with_no_sentence_terminator() -> None:
    # Splitting is structural (heading / blank-line), never lexical — this
    # section has no `.`/`!`/`?` anywhere, yet still splits on its paragraph
    # (blank-line) boundaries.
    bullet_line = "- item without any sentence terminator here\n"
    block1 = bullet_line * 25
    block2 = bullet_line * 25
    section = "## Y\n\n" + block1 + "\n" + block2
    assert len(section) > MAX_CHUNK_CHARS
    assert "." not in section and "!" not in section and "?" not in section

    chunks = chunk_markdown(section)

    assert len(chunks) == 2


def test_chunk_markdown_treats_a_blank_line_of_only_spaces_or_tabs_as_a_paragraph_separator() -> (
    None
):
    section = "## Z\n\n" + "a" * 1200 + "\n   \t \n" + "b" * 1200

    chunks = chunk_markdown(section)

    assert len(chunks) == 2
    assert "a" * 1200 in chunks[0]
    assert "b" * 1200 in chunks[1]


# --- Phase 5: fenced code blocks (`_fenced_spans` / `_headings`) ------------


def test_chunk_markdown_ignores_a_hash_comment_inside_a_backtick_fence() -> None:
    doc = "## A\nbody a\n```sh\n# not a heading\necho hi\n```\n## B\nbody b\n"

    chunks = chunk_markdown(doc)

    assert len(chunks) == 2
    assert chunks[0].startswith("## A")
    assert chunks[1].startswith("## B")


def test_chunk_markdown_ignores_heading_like_lines_inside_a_tilde_fence() -> None:
    doc = "## A\nbody a\n~~~\n## not a heading either\n~~~\n## B\nbody b\n"

    chunks = chunk_markdown(doc)

    assert len(chunks) == 2
    assert chunks[0].startswith("## A")
    assert chunks[1].startswith("## B")


def test_chunk_markdown_does_not_close_a_backtick_fence_with_a_tilde_fence() -> None:
    doc = "## A\n```\ncode\n~~~\nmore code\n```\n## B\nb\n"

    chunks = chunk_markdown(doc)

    assert len(chunks) == 2
    assert "~~~" in chunks[0]
    assert chunks[1].startswith("## B")


def test_chunk_markdown_recognizes_a_fence_indented_up_to_three_spaces() -> None:
    doc = "## A\n   ```\ncode\n   ```\n## B\nb\n"

    chunks = chunk_markdown(doc)

    assert len(chunks) == 2


def test_chunk_markdown_does_not_treat_a_four_space_indented_fence_as_a_fence() -> None:
    # Paired negative case for the previous test: at 4 spaces the marker no
    # longer gates heading detection, so the heading-like line inside it is
    # treated as a real heading and starts its own chunk.
    doc = "## A\n    ```\n## still a heading\n    ```\n## B\nb\n"

    chunks = chunk_markdown(doc)

    assert len(chunks) == 3
    assert chunks[1].startswith("## still a heading")


def test_chunk_markdown_recognizes_a_fence_opened_with_an_info_string_and_more_backticks() -> None:
    doc = "## A\n````python\n# not heading\n````\n## B\nb\n"

    chunks = chunk_markdown(doc)

    assert len(chunks) == 2
    assert chunks[0].startswith("## A")
    assert chunks[1].startswith("## B")


def test_chunk_markdown_swallows_the_rest_of_the_document_when_a_fence_is_never_closed() -> None:
    # Deliberate current behaviour, not a regression: an unclosed fence
    # extends to end-of-text and silently merges every following section —
    # including "## B" — into a single chunk.
    doc = "## A\n```\ncode\n\n## B\nb\n"

    chunks = chunk_markdown(doc)

    assert chunks == [doc]


# --- Phase 6: line endings and whitespace -----------------------------------


def test_chunk_markdown_splits_normally_with_crlf_line_endings() -> None:
    doc = "## A\r\nbody a\r\n\r\n## B\r\nbody b\r\n"

    chunks = chunk_markdown(doc)

    assert len(chunks) == 2
    assert chunks[0].startswith("## A")
    assert chunks[1].startswith("## B")


def test_chunk_markdown_preserves_trailing_whitespace_while_dropping_a_blank_tail_piece() -> None:
    doc = "   \n\n## A\nbody with trailing spaces   \n"

    chunks = chunk_markdown(doc)

    assert chunks == ["## A\nbody with trailing spaces   \n"]


# --- Phase 7: output list contract (`chunk_index` dependency) --------------


def test_chunk_markdown_returns_chunks_in_source_order() -> None:
    doc = "Preamble.\n\n## A\nbody a\n\n## B\nbody b\n\n## C\nbody c\n"

    chunks = chunk_markdown(doc)

    offsets = [doc.index(chunk.strip().splitlines()[0]) for chunk in chunks]
    assert offsets == sorted(offsets)
    assert len(set(offsets)) == len(offsets)


def test_chunk_markdown_concatenation_reproduces_the_source_on_the_heading_path() -> None:
    doc = "## A\nx\n\n## B\ny\n"

    chunks = chunk_markdown(doc)

    assert "".join(chunks) == doc


def test_chunk_markdown_does_not_duplicate_content_across_chunks_on_the_paragraph_path() -> None:
    para1 = "First paragraph marker ONE. " * 40
    para2 = "Second paragraph marker TWO. " * 40
    section = "## X\n\n" + para1 + "\n\n" + para2
    assert len(section) > MAX_CHUNK_CHARS

    chunks = chunk_markdown(section)

    assert sum("ONE" in chunk for chunk in chunks) == 1
    assert sum("TWO" in chunk for chunk in chunks) == 1


def test_chunk_markdown_returns_no_blank_or_whitespace_only_chunk_for_any_fixture() -> None:
    fixtures = [
        MULTI_SECTION_DOC,
        OVERSIZED_SECTION,
        "## A\n## B\n",
        "   \n\n## A\nbody\n",
        "## A\r\nbody a\r\n\r\n## B\r\nbody b\r\n",
        "## A\n```\ncode\n\n## B\nb\n",
    ]

    for fixture in fixtures:
        for chunk in chunk_markdown(fixture):
            assert chunk.strip()
