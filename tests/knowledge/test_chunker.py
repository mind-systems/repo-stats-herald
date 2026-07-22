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
