"""
Versioned-name keys for joining items about the same release.

Embedding similarity alone can't tell "Gemini 3.8 Live" from
another Gemini post, and HF model cards all look alike. A
shared versioned name ("gemini 3.8", "qwen image 2.1",
"mimo v2.6") is a much sharper signal, so clustering uses it
alongside similarity.
"""

from __future__ import annotations

import re


_SPLIT = re.compile(
    r"[\s\-_/:,;()\[\]{}\"'“”‘’!?|&+]+"
)

_YEAR = re.compile(r"^(19|20)\d\d$")

# Parameter counts / sizes ("9b", "27b", "8x7b", "128k"):
# they describe a variant, not the product.
_SIZE = re.compile(r"^(\d+x)?\d+(\.\d+)?[bmk]$")

_STOP = {
    "a", "an", "and", "are", "at", "by", "for", "from", "in",
    "into", "is", "its", "of", "on", "or", "our", "over", "than",
    "the", "to", "top", "up", "via", "vs", "with", "about",
    "introducing", "meet", "new", "how", "why", "what", "releases",
    "release", "launches", "launch", "announces", "says", "using",
    "first", "last", "next", "every", "all", "only", "just", "after",
}


def _tokens(
    text: str,
) -> list[str]:
    return [
        token.strip(".")
        for token in _SPLIT.split(text.lower())
        if token.strip(".")
    ]


def _has_digit(
    token: str,
) -> bool:
    return any(char.isdigit() for char in token)


def _is_name_word(
    token: str,
) -> bool:
    return token.isalpha() and token not in _STOP


def entity_keys(
    text: str,
) -> set[str]:
    """
    Keys for every versioned token plus up to two preceding
    name words:

        "Introducing Gemini 3.8 Live" -> {"gemini 3.8", ...}
        "unsloth/Qwen-Image-2.1-GGUF" -> {"image 2.1", "qwen image 2.1"}
        "Qwen3.8-27B"                 -> {"qwen3.8"}
    """

    tokens = _tokens(text)
    keys: set[str] = set()

    for index, token in enumerate(tokens):
        if not _has_digit(token):
            continue

        if _YEAR.match(token) or _SIZE.match(token) or token.endswith("%"):
            continue

        # Self-contained names: qwen3, gpt4o, llama4.
        if sum(char.isalpha() for char in token) >= 3:
            keys.add(token)

        if index >= 1 and _is_name_word(tokens[index - 1]):
            keys.add(f"{tokens[index - 1]} {token}")

            if index >= 2 and _is_name_word(tokens[index - 2]):
                keys.add(
                    f"{tokens[index - 2]} {tokens[index - 1]} {token}"
                )

    return keys


def is_strong_key(
    key: str,
) -> bool:
    """
    Specific enough to identify one release on its own:
    three words ("claude opus 5.5") or a dotted version
    ("gemini 3.8", "qwen3.8"). Bare integers ("gpt 6") are
    weak: many different GPT-6 stories exist in one week.
    """

    parts = key.split()

    return len(parts) >= 3 or "." in parts[-1]
