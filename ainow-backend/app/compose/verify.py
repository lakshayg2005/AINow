"""
Deterministic fact guard for generated text.

Invented numbers are the most damaging hallucination in a
news summary ("3x faster", "92% on MMLU"). Every multi-digit,
decimal, percentage or multiplier in generated text must
appear in the context the writer was given; sentences that
contain one that doesn't are removed.
"""

from __future__ import annotations

import re


_NUMBER = re.compile(
    r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)(\s?%|x\b|×)?"
)

_SENTENCE_SPLIT = re.compile(
    r"(?<=[.!?])\s+(?=[A-Z0-9\"'“(])"
)


def _normalize(
    number: str,
) -> str:
    return number.replace(",", "")


def claim_numbers(
    text: str,
) -> list[str]:
    """
    Numbers worth checking. Single digits are skipped: they
    appear in names ("GPT-6") and prose too often to verify.
    """

    numbers = []

    for match in _NUMBER.finditer(text or ""):
        value = _normalize(match.group(1)).rstrip(".")

        if len(value) == 1 and not match.group(2):
            continue

        numbers.append(value)

    return numbers


def _context_numbers(
    context: str,
) -> set[str]:
    return {
        _normalize(match.group(1)).rstrip(".")
        for match in _NUMBER.finditer(context or "")
    }


def unsupported_numbers(
    text: str,
    context: str,
) -> list[str]:
    known = _context_numbers(context)

    return [
        number
        for number in claim_numbers(text)
        if number not in known
    ]


def strip_unsupported(
    text: str,
    context: str,
) -> tuple[str, int]:
    """
    Remove sentences containing numbers absent from the
    context. Returns (clean_text, sentences_removed).
    """

    if not text:
        return text, 0

    known = _context_numbers(context)
    kept: list[str] = []
    removed = 0

    for sentence in _SENTENCE_SPLIT.split(text.strip()):
        if any(number not in known for number in claim_numbers(sentence)):
            removed += 1
            print(f"[Verify] removed: {sentence[:120]}")
            continue

        kept.append(sentence)

    return " ".join(kept), removed
