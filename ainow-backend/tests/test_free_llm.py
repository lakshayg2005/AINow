"""
Offline tests for the free-tier LLM provider chain: fallback,
cooldown, rate-limit waiting and JSON-repair retry (mocked chat
model calls, no network).

    pytest tests/test_free_llm.py
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
from langchain_openai.chat_models.base import OpenAIRateLimitError

from app.core import free_llm
from app.core.config import settings


PROVIDER_KEYS = (
    "groq_api_key",
    "cerebras_api_key",
    "gemini_api_key",
    "openrouter_api_key",
    "ollama_base_url",
)

# hf_token is a required (non-Optional) setting, always a real
# value from .env; clear it too so "hf" never sneaks into a
# chain meant to be empty or single-provider in these tests.
_UNSET = {**{key: None for key in PROVIDER_KEYS}, "hf_token": ""}


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChatOpenAI:
    """Stands in for langchain_openai.ChatOpenAI: `.ainvoke`
    replays one scripted outcome per call from a per-provider
    queue, so tests never touch the network."""

    def __init__(self, script: list, calls: list, **kwargs):
        self._script = script
        self._calls = calls
        self.kwargs = kwargs

    async def ainvoke(self, messages):
        self._calls.append(messages)
        outcome = self._script.pop(0)

        if isinstance(outcome, Exception):
            raise outcome

        return _FakeMessage(outcome)


def _only_providers(monkeypatch, *names: str):
    """Configure exactly these providers (in DEFAULT_ORDER), so
    build_chain resolves deterministically for a test."""

    for key, value in _UNSET.items():
        monkeypatch.setattr(settings, key, value)

    for name in names:
        key = "ollama_base_url" if name == "ollama" else f"{name}_api_key"
        monkeypatch.setattr(settings, key, "test-value")


def _install_fake(monkeypatch, *scripts: list):
    """One script (list of canned replies/exceptions) per
    provider expected to be tried, in chain order."""

    calls: list = []
    queue = [list(script) for script in scripts]

    def factory(**kwargs):
        return _FakeChatOpenAI(queue.pop(0), calls, **kwargs)

    monkeypatch.setattr(free_llm, "ChatOpenAI", factory)
    return calls


def _rate_limit_error(retry_after: str) -> OpenAIRateLimitError:
    request = httpx.Request("POST", "http://example.com")
    response = httpx.Response(429, request=request, headers={"retry-after": retry_after})
    return OpenAIRateLimitError("rate limited", response=response, body=None)


@pytest.fixture(autouse=True)
def _clear_cooldowns():
    free_llm._cooldown.clear()
    yield
    free_llm._cooldown.clear()


# ============================================================
# Happy path
# ============================================================

def test_chat_json_returns_parsed_json_and_label(monkeypatch):
    _only_providers(monkeypatch, "groq")
    _install_fake(monkeypatch, ['{"a": 1}'])

    data, label = asyncio.run(
        free_llm.chat_json([{"role": "user", "content": "hi"}])
    )

    assert data == {"a": 1}
    assert label == "groq:openai/gpt-oss-20b"


# ============================================================
# Fallback + cooldown
# ============================================================

def test_chat_json_falls_back_to_next_provider_on_failure(monkeypatch):
    _only_providers(monkeypatch, "groq", "cerebras")
    _install_fake(
        monkeypatch,
        [httpx.HTTPError("boom")],
        ['{"b": 2}'],
    )

    data, label = asyncio.run(
        free_llm.chat_json([{"role": "user", "content": "hi"}])
    )

    assert data == {"b": 2}
    assert label == "cerebras:llama3.1-8b"
    assert "groq" in free_llm._cooldown


def test_chat_json_skips_provider_still_in_cooldown(monkeypatch):
    _only_providers(monkeypatch, "groq", "cerebras")
    free_llm._cooldown["groq"] = free_llm.time.monotonic() + 60

    _install_fake(monkeypatch, ['{"b": 2}'])

    data, label = asyncio.run(
        free_llm.chat_json([{"role": "user", "content": "hi"}])
    )

    assert data == {"b": 2}
    assert label == "cerebras:llama3.1-8b"


def test_chat_json_raises_when_every_provider_fails(monkeypatch):
    _only_providers(monkeypatch, "groq")
    _install_fake(monkeypatch, [httpx.HTTPError("boom")])

    with pytest.raises(free_llm.LLMUnavailable, match="groq"):
        asyncio.run(free_llm.chat_json([{"role": "user", "content": "hi"}]))


def test_chat_json_raises_with_no_provider_configured(monkeypatch):
    _only_providers(monkeypatch)

    with pytest.raises(free_llm.LLMUnavailable):
        asyncio.run(free_llm.chat_json([{"role": "user", "content": "hi"}]))


# ============================================================
# Malformed JSON retry
# ============================================================

def test_chat_json_retries_once_on_malformed_json_then_succeeds(monkeypatch):
    _only_providers(monkeypatch, "groq")
    calls = _install_fake(monkeypatch, ["not json", '{"ok": true}'])

    data, label = asyncio.run(
        free_llm.chat_json([{"role": "user", "content": "hi"}])
    )

    assert data == {"ok": True}
    assert label == "groq:openai/gpt-oss-20b"
    assert len(calls) == 2
    # The retry feeds the bad reply + a correction back to the model.
    assert calls[1][-1].content.startswith("That was not valid JSON")


def test_chat_json_gives_up_after_one_bad_json_retry(monkeypatch):
    _only_providers(monkeypatch, "groq")
    _install_fake(monkeypatch, ["not json", "still not json"])

    with pytest.raises(free_llm.LLMUnavailable, match="bad JSON"):
        asyncio.run(free_llm.chat_json([{"role": "user", "content": "hi"}]))


# ============================================================
# Rate limits
# ============================================================

def test_chat_json_waits_out_a_short_rate_limit_then_succeeds(monkeypatch):
    _only_providers(monkeypatch, "groq")
    monkeypatch.setattr(free_llm.asyncio, "sleep", _record_sleep())
    _install_fake(monkeypatch, [_rate_limit_error("1"), '{"ok": true}'])

    data, label = asyncio.run(
        free_llm.chat_json([{"role": "user", "content": "hi"}])
    )

    assert data == {"ok": True}
    assert label == "groq:openai/gpt-oss-20b"


def test_chat_json_gives_up_on_a_long_rate_limit_wait(monkeypatch):
    _only_providers(monkeypatch, "groq")
    monkeypatch.setattr(free_llm.asyncio, "sleep", _record_sleep())
    _install_fake(monkeypatch, [_rate_limit_error("9999")])

    with pytest.raises(free_llm.LLMUnavailable):
        asyncio.run(free_llm.chat_json([{"role": "user", "content": "hi"}]))


def _record_sleep():
    async def _sleep(seconds):
        return None

    return _sleep


# ============================================================
# Per-model quirks
# ============================================================

def test_qwen3_gets_no_think_suffix_on_last_message(monkeypatch):
    monkeypatch.setattr(settings, "llm_fast_chain", "ollama:qwen3:8b")
    monkeypatch.setattr(settings, "ollama_base_url", "http://localhost:11434")
    calls = _install_fake(monkeypatch, ['{"ok": true}'])

    asyncio.run(
        free_llm.chat_json(
            [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "hi"},
            ],
            tier="fast",
        )
    )

    assert calls[0][-1].content == "hi\n\n/no_think"
    assert calls[0][0].content == "system"
