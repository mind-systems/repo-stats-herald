MAX_CHUNK_CHARS = 2000


def chunk_markdown(text: str) -> list[str]:
    """Split a Markdown document on headings into whole sections (heading
    line + its body kept together as one chunk), so a retrieved chunk keeps
    its point rather than a fixed-window fragment.

    A section longer than `MAX_CHUNK_CHARS` is oversized and must be split
    further on sub-headings / paragraph boundaries, never mid-sentence. A
    section `<= MAX_CHUNK_CHARS` stays a single chunk.
    """
    raise NotImplementedError
