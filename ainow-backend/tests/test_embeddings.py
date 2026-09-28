"""
Offline tests for the embeddings module: provider switching and
the Hugging Face Inference API backend (mocked, no network, no
model download).

    pytest tests/test_embeddings.py
"""

import math

import httpx
import pytest

from app.core import embeddings
from app.core.config import settings


def _mock_client(handler, monkeypatch):
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))


def _unit(*values: float) -> list[float]:
    """A pre-normalized vector, for equality checks."""

    norm = math.sqrt(sum(v * v for v in values))
    return [v / norm for v in values]


# ============================================================
# Pooling
# ============================================================

def test_pooled_normalizes_already_pooled_vectors():
    result = embeddings._pooled([[3.0, 4.0], [1.0, 0.0]])

    assert result[0] == pytest.approx([0.6, 0.8])
    assert result[1] == pytest.approx([1.0, 0.0])


def test_pooled_mean_pools_token_level_vectors():
    # One input, two tokens; mean is [2.0, 2.0] -> normalized [~0.707, ~0.707].
    result = embeddings._pooled([[[1.0, 3.0], [3.0, 1.0]]])

    assert result[0] == pytest.approx(_unit(1.0, 1.0))


def test_pooled_rejects_empty_or_wrong_shape():
    with pytest.raises(ValueError):
        embeddings._pooled([])

    with pytest.raises(ValueError):
        embeddings._pooled("not a list")


# ============================================================
# Hugging Face backend
# ============================================================

def test_hf_embed_success(monkeypatch):
    monkeypatch.setattr(settings, "hf_token", "hf_test_token")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer hf_test_token"
        return httpx.Response(200, json=[[3.0, 4.0]])

    _mock_client(handler, monkeypatch)

    [vector] = embeddings._hf_embed(["hello"])
    assert vector == pytest.approx([0.6, 0.8])


def test_hf_embed_requires_token(monkeypatch):
    monkeypatch.setattr(settings, "hf_token", "")

    with pytest.raises(RuntimeError, match="HF_TOKEN"):
        embeddings._hf_embed(["hello"])


def test_hf_embed_raises_clearly_on_exhausted_credits(monkeypatch):
    monkeypatch.setattr(settings, "hf_token", "hf_test_token")
    _mock_client(lambda request: httpx.Response(402, json={"error": "credits"}), monkeypatch)

    with pytest.raises(RuntimeError, match="credits exhausted"):
        embeddings._hf_embed(["hello"])


def test_hf_embed_retries_rate_limit_then_succeeds(monkeypatch):
    monkeypatch.setattr(settings, "hf_token", "hf_test_token")
    monkeypatch.setattr(embeddings.time, "sleep", lambda seconds: None)

    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1

        if calls["count"] < 3:
            return httpx.Response(429, json={"error": "rate limited"})

        return httpx.Response(200, json=[[1.0, 0.0]])

    _mock_client(handler, monkeypatch)

    [vector] = embeddings._hf_embed(["hello"])
    assert vector == pytest.approx([1.0, 0.0])
    assert calls["count"] == 3


def test_hf_embed_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr(settings, "hf_token", "hf_test_token")
    monkeypatch.setattr(embeddings.time, "sleep", lambda seconds: None)
    _mock_client(lambda request: httpx.Response(500, text="down"), monkeypatch)

    with pytest.raises(RuntimeError, match="failed after 3 attempts"):
        embeddings._hf_embed(["hello"])


# ============================================================
# Provider switching (generate_embedding / generate_embeddings)
# ============================================================

def test_generate_embeddings_empty_list_short_circuits(monkeypatch):
    # Should not call either backend at all.
    monkeypatch.setattr(embeddings, "_embed_batch", lambda texts: (_ for _ in ()).throw(AssertionError("called")))
    assert embeddings.generate_embeddings([]) == []


def test_generate_embedding_uses_configured_provider(monkeypatch):
    seen = []

    def fake_local(texts):
        seen.append(("local", texts))
        return [[1.0]]

    def fake_hf(texts):
        seen.append(("hf", texts))
        return [[2.0]]

    monkeypatch.setattr(embeddings, "_local_embed", fake_local)
    monkeypatch.setattr(embeddings, "_hf_embed", fake_hf)

    monkeypatch.setattr(settings, "embeddings_provider", "local")
    assert embeddings.generate_embedding("x") == [1.0]
    assert seen == [("local", ["x"])]

    seen.clear()
    monkeypatch.setattr(settings, "embeddings_provider", "hf")
    assert embeddings.generate_embedding("x") == [2.0]
    assert seen == [("hf", ["x"])]
