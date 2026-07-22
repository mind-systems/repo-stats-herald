import re

MAX_CHUNK_CHARS = 2000

_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+\S.*$", re.MULTILINE)
_FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})", re.MULTILINE)


def chunk_markdown(text: str) -> list[str]:
    """Split a Markdown document on headings into whole sections (heading
    line + its body kept together as one chunk), so a retrieved chunk keeps
    its point rather than a fixed-window fragment.

    A section longer than `MAX_CHUNK_CHARS` is oversized and must be split
    further on sub-headings / paragraph boundaries, never mid-sentence. A
    section `<= MAX_CHUNK_CHARS` stays a single chunk.
    """
    sections = _split_at_min_level_headings(text, skip_first=False)
    if sections is None:
        sections = [text] if text.strip() else []

    chunks: list[str] = []
    for section in sections:
        chunks.extend(_ensure_size(section))
    return [chunk for chunk in chunks if chunk.strip()]


def _headings(text: str) -> list[tuple[int, int]]:
    """`(start_index, level)` for each heading line in `text`, in order.
    Lines inside fenced code blocks (```` ``` ````/`~~~`) are never headings
    — a `#` code comment at column 0 is not a Markdown heading."""
    fenced = _fenced_spans(text)
    return [
        (match.start(), len(match.group(1)))
        for match in _HEADING_RE.finditer(text)
        if not any(start <= match.start() < end for start, end in fenced)
    ]


def _fenced_spans(text: str) -> list[tuple[int, int]]:
    """`(start_index, end_index)` for each fenced code block in `text`, from
    its opening fence line through its matching closing fence line (or
    end-of-text if the fence is never closed)."""
    spans = []
    pos = 0
    open_marker: str | None = None
    open_pos = 0
    for line in text.splitlines(keepends=True):
        match = _FENCE_RE.match(line)
        if match:
            marker = match.group(1)[0]
            if open_marker is None:
                open_marker = marker
                open_pos = pos
            elif marker == open_marker:
                spans.append((open_pos, pos + len(line)))
                open_marker = None
        pos += len(line)
    if open_marker is not None:
        spans.append((open_pos, len(text)))
    return spans


def _split_at_min_level_headings(text: str, skip_first: bool) -> list[str] | None:
    """Split `text` into whole sections at its shallowest heading level: a
    heading plus its body up to (but not including) the next heading of the
    same-or-shallower level. Text before the first split point, if
    non-blank, becomes its own leading piece.

    `skip_first` ignores a heading sitting at index 0 — used when
    re-splitting a section on its *nested* sub-headings, where the
    section's own opening heading must not be mistaken for the split level.

    Returns `None` when there is nothing to split on (no headings, or only
    the section's own leading heading with `skip_first=True`).
    """
    headings = _headings(text)
    if skip_first:
        headings = [(pos, level) for pos, level in headings if pos > 0]
    if not headings:
        return None

    min_level = min(level for _, level in headings)
    starts = [pos for pos, level in headings if level == min_level]

    pieces = []
    if starts[0] > 0:
        pieces.append(text[: starts[0]])
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(text)
        pieces.append(text[start:end])

    return [piece for piece in pieces if piece.strip()]


def _ensure_size(section: str) -> list[str]:
    if len(section) <= MAX_CHUNK_CHARS:
        return [section]

    sub_pieces = _split_at_min_level_headings(section, skip_first=True)
    if sub_pieces is not None:
        result: list[str] = []
        for piece in sub_pieces:
            result.extend(_ensure_size(piece))
        return result

    return _split_by_paragraphs(section)


def _split_by_paragraphs(section: str) -> list[str]:
    """Last-resort split for a heading-less, still-oversized leaf: greedily
    group whole paragraphs (blank-line separated) up to `MAX_CHUNK_CHARS`.
    A single paragraph that alone exceeds the limit is kept intact rather
    than cut mid-sentence.
    """
    paragraphs = [p for p in re.split(r"\n\s*\n", section) if p.strip()]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if current and len(candidate) > MAX_CHUNK_CHARS:
            chunks.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
