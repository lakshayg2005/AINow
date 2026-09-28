from __future__ import annotations

import os
from typing import TYPE_CHECKING

from app.core.config import settings

# Importing sentence_transformers (and torch) takes ~10s, so
# it happens on first use rather than at API startup.
if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


# The model download reads HF_TOKEN from the environment, not
# from .env; without it the Hub warns about anonymous requests.
if settings.hf_token:
    os.environ.setdefault("HF_TOKEN", settings.hf_token)


MODEL_NAME = "all-MiniLM-L6-v2"

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model

    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME)

    return _model


def generate_embedding(
    text: str,
) -> list[float]:
    model = _get_model()

    embedding = model.encode(
        text,
        normalize_embeddings=True,
    )

    return embedding.tolist()


def generate_embeddings(
    texts: list[str],
) -> list[list[float]]:
    model = _get_model()

    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
    )

    return embeddings.tolist()