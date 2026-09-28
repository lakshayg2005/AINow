"""
Text embeddings for search, clustering and RAG retrieval.

Two backends behind the same generate_embedding[s] interface,
picked by EMBEDDINGS_PROVIDER:

  local (default) - runs sentence-transformers/all-MiniLM-L6-v2
                     in this process. Fast and free, but the
                     model needs more memory than a free-tier
                     host (e.g. Render's 512MB) reliably has —
                     it was hanging ingest indefinitely there.
  hf               - calls the same model through Hugging
                      Face's free hosted Inference API instead,
                      so nothing heavy loads into this process.
                      Same model, same 384 dimensions, so it's a
                      drop-in swap: no re-embedding, no schema
                      change.

Set EMBEDDINGS_PROVIDER=hf on a memory-constrained host.
"""

from __future__ import annotations

import math
import os
import time
from typing import TYPE_CHECKING

import httpx

from app.core.config import settings

# Importing sentence_transformers (and torch) takes ~10s, so it
# happens on first use rather than at API startup, and only in
# "local" mode.
if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


MODEL_NAME = "all-MiniLM-L6-v2"
HF_MODEL_PATH = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS = 384

# The model download reads HF_TOKEN from the environment, not
# from .env; without it the Hub warns about anonymous requests.
if settings.hf_token:
    os.environ.setdefault("HF_TOKEN", settings.hf_token)


# ============================================================
# Local (in-process) backend
# ============================================================

_model: "SentenceTransformer | None" = None


def _get_model() -> "SentenceTransformer":
    global _model

    if _model is None:
        print(f"[Embeddings] Loading {MODEL_NAME} (first use this run)...")

        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME)

        print("[Embeddings] Model loaded.")

    return _model


def _local_embed(
    texts: list[str],
) -> list[list[float]]:
    model = _get_model()

    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
    )

    return embeddings.tolist()


# ============================================================
# Remote backend (Hugging Face Inference API)
# ============================================================

HF_INFERENCE_URL = (
    f"https://router.huggingface.co/hf-inference/models/{HF_MODEL_PATH}"
    "/pipeline/feature-extraction"
)

# wait_for_model below already covers a cold model; this only
# covers transient network/rate-limit trouble on top of that.
HF_RETRIES = 3


def _normalize(
    vector: list[float],
) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def _pooled(
    raw: object,
) -> list[list[float]]:
    """
    sentence-transformers models normally come back already
    pooled to one vector per input (list[list[float]]). Some
    Inference API paths instead return per-token vectors
    (list[list[list[float]]]) — mean-pool those ourselves so
    either shape ends up the same as the local backend's output.
    """

    if not isinstance(raw, list) or not raw:
        raise ValueError(f"Unexpected embeddings response shape: {type(raw)}")

    if isinstance(raw[0][0], (int, float)):
        return [_normalize(vector) for vector in raw]

    pooled = []

    for token_vectors in raw:
        width = len(token_vectors[0])
        summed = [0.0] * width

        for token_vector in token_vectors:
            for index, value in enumerate(token_vector):
                summed[index] += value

        pooled.append(_normalize([value / len(token_vectors) for value in summed]))

    return pooled


def _hf_embed(
    texts: list[str],
) -> list[list[float]]:
    if not settings.hf_token:
        raise RuntimeError(
            "EMBEDDINGS_PROVIDER=hf requires HF_TOKEN to be set."
        )

    last_error: Exception | None = None

    with httpx.Client(
        headers={"Authorization": f"Bearer {settings.hf_token}"},
        # Generous: wait_for_model can mean a genuine cold start
        # (the model spinning up on HF's side) on top of network time.
        timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=30.0),
    ) as client:
        for attempt in range(1, HF_RETRIES + 1):
            try:
                response = client.post(
                    HF_INFERENCE_URL,
                    json={"inputs": texts, "options": {"wait_for_model": True}},
                )

                if response.status_code == 402:
                    raise RuntimeError(
                        "Hugging Face Inference API: free credits exhausted (402). "
                        "Try a different EMBEDDINGS_PROVIDER."
                    )

                if response.status_code in (401, 403):
                    raise RuntimeError(
                        f"Hugging Face Inference API: HF_TOKEN rejected ({response.status_code})."
                    )

                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )

                response.raise_for_status()

                return _pooled(response.json())

            except (httpx.HTTPStatusError, httpx.TransportError) as error:
                last_error = error

                if attempt < HF_RETRIES:
                    time.sleep(2**attempt)

    assert last_error is not None
    raise RuntimeError(
        f"Hugging Face Inference API failed after {HF_RETRIES} attempts: {last_error}"
    ) from last_error


# ============================================================
# Public interface (unchanged by provider)
# ============================================================

def _embed_batch(
    texts: list[str],
) -> list[list[float]]:
    if settings.embeddings_provider == "hf":
        return _hf_embed(texts)

    return _local_embed(texts)


def generate_embedding(
    text: str,
) -> list[float]:
    return _embed_batch([text])[0]


def generate_embeddings(
    texts: list[str],
) -> list[list[float]]:
    if not texts:
        return []

    return _embed_batch(texts)
