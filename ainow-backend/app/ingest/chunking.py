from __future__ import annotations

import re


TARGET_CHUNK_CHARS = 1000
MAX_CHUNK_CHARS = 1500
OVERLAP_CHARS = 150
MAX_CHUNKS_PER_ITEM = 20


def _split_long_paragraph(
    paragraph: str,
) -> list[str]:
    """
    Split an oversized paragraph on sentence boundaries.
    """

    sentences = re.split(
        r"(?<=[.!?])\s+",
        paragraph,
    )

    pieces: list[str] = []
    current = ""

    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > MAX_CHUNK_CHARS:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()

    if current:
        pieces.append(current)

    # A single "sentence" longer than the cap (tables, code).
    return [
        piece[start:start + MAX_CHUNK_CHARS]
        for piece in pieces
        for start in range(0, len(piece), MAX_CHUNK_CHARS)
    ]


def chunk_text(
    text: str | None,
) -> list[str]:
    """
    Pack paragraphs into ~1000-char chunks, carrying a short
    tail of the previous chunk forward so a fact that spans a
    boundary is still retrievable.
    """

    if not text or not text.strip():
        return []

    paragraphs: list[str] = []

    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()

        if not paragraph:
            continue

        if len(paragraph) > MAX_CHUNK_CHARS:
            paragraphs.extend(
                _split_long_paragraph(paragraph)
            )
        else:
            paragraphs.append(paragraph)

    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 2 > TARGET_CHUNK_CHARS:
            chunks.append(current)

            tail = current[-OVERLAP_CHARS:]
            tail = tail[tail.find(" ") + 1:] if " " in tail else tail
            current = f"{tail}\n\n{paragraph}"
        else:
            current = (
                f"{current}\n\n{paragraph}"
                if current
                else paragraph
            )

        if len(chunks) >= MAX_CHUNKS_PER_ITEM:
            break

    if current and len(chunks) < MAX_CHUNKS_PER_ITEM:
        chunks.append(current)

    return chunks
