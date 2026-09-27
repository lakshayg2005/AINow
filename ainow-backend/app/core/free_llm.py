"""
Free-tier LLM access with provider fallback.

Every provider below exposes an OpenAI-compatible
/chat/completions endpoint, so one small client covers all
of them. Providers are tried in order; a provider that
rate-limits or errors is skipped for the rest of the process.

Tiers:
    fast   - cheap classification (triage)
    strong - writing and judging

Model names on free tiers change often. Override any chain
in .env, e.g.

    LLM_FAST_CHAIN=groq:openai/gpt-oss-20b,hf:Qwen/Qwen3-8B
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.core.config import settings


Tier = Literal["fast", "strong"]


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    api_key: str | None
    fast_model: str
    strong_model: str
    json_mode: bool = True


def _providers() -> dict[str, Provider]:
    return {
        "groq": Provider(
            name="groq",
            base_url="https://api.groq.com/openai/v1",
            api_key=settings.groq_api_key,
            fast_model="openai/gpt-oss-20b",
            strong_model="openai/gpt-oss-120b",
        ),
        "cerebras": Provider(
            name="cerebras",
            base_url="https://api.cerebras.ai/v1",
            api_key=settings.cerebras_api_key,
            fast_model="llama3.1-8b",
            strong_model="llama-3.3-70b",
        ),
        "gemini": Provider(
            name="gemini",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            api_key=settings.gemini_api_key,
            fast_model="gemini-2.5-flash-lite",
            strong_model="gemini-2.5-flash",
        ),
        "openrouter": Provider(
            name="openrouter",
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key,
            fast_model="meta-llama/llama-3.3-70b-instruct:free",
            strong_model="meta-llama/llama-3.3-70b-instruct:free",
        ),
        "hf": Provider(
            name="hf",
            base_url="https://router.huggingface.co/v1",
            api_key=settings.hf_token,
            fast_model=settings.hf_model_id,
            strong_model="meta-llama/Llama-3.3-70B-Instruct",
            # Support varies by the underlying HF provider.
            json_mode=False,
        ),
        "ollama": Provider(
            name="ollama",
            base_url=(settings.ollama_base_url or "").rstrip("/") + "/v1",
            api_key="ollama",
            fast_model="qwen3:8b",
            strong_model="qwen3:14b",
        ),
    }


DEFAULT_ORDER = (
    "groq",
    "cerebras",
    "gemini",
    "openrouter",
    "hf",
    "ollama",
)


def _is_configured(
    provider: Provider,
) -> bool:
    if provider.name == "ollama":
        return bool(settings.ollama_base_url)

    return bool(provider.api_key)


def build_chain(
    tier: Tier,
) -> list[tuple[Provider, str]]:
    """
    Resolve the (provider, model) fallback chain for a tier.
    """

    providers = _providers()

    explicit = (
        settings.llm_fast_chain
        if tier == "fast"
        else settings.llm_strong_chain
    )

    if explicit:
        chain = []

        for entry in explicit.split(","):
            name, _, model = entry.strip().partition(":")
            provider = providers.get(name)

            if provider and model and _is_configured(provider):
                chain.append((provider, model))

        return chain

    return [
        (
            provider,
            provider.fast_model
            if tier == "fast"
            else provider.strong_model,
        )
        for name in DEFAULT_ORDER
        if _is_configured(provider := providers[name])
    ]


# ============================================================
# JSON extraction
# ============================================================

_THINK = re.compile(
    r"<think>.*?</think>",
    re.DOTALL,
)

_FENCE = re.compile(
    r"^```(?:json)?\s*|\s*```$",
)


def extract_json(
    text: str,
) -> Any:
    """
    Parse a JSON object/array from model output, tolerating
    <think> blocks, code fences and surrounding prose.
    """

    text = _THINK.sub("", text or "").strip()
    text = _FENCE.sub("", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    starts = [
        index
        for index in (text.find("{"), text.find("["))
        if index != -1
    ]

    if not starts:
        raise ValueError("No JSON found in model output")

    start = min(starts)
    closer = "}" if text[start] == "{" else "]"
    end = text.rfind(closer)

    if end <= start:
        raise ValueError("Unterminated JSON in model output")

    return json.loads(text[start:end + 1])


# ============================================================
# Client
# ============================================================

class LLMUnavailable(RuntimeError):
    pass


# Providers that failed hard in this process: {name: until}.
_cooldown: dict[str, float] = {}

COOLDOWN_SECONDS = 300


# Free tiers limit tokens per minute; waiting out a short
# window is far better than dropping to a weaker provider.
MAX_RATE_LIMIT_WAIT = 75
RATE_LIMIT_RETRIES = 3

_RETRY_IN = re.compile(r"try again in (?:(\d+)m)?([\d.]+)s", re.IGNORECASE)


def _retry_after_seconds(
    response: httpx.Response,
) -> float | None:
    header = response.headers.get("retry-after")

    if header:
        try:
            return float(header)
        except ValueError:
            pass

    match = _RETRY_IN.search(response.text)

    if match:
        return int(match.group(1) or 0) * 60 + float(match.group(2))

    return None


async def _post_with_retry(
    client: httpx.AsyncClient,
    url: str,
    api_key: str | None,
    payload: dict[str, Any],
    attempts: int = 3,
) -> httpx.Response:
    """
    Retry dropped connections, and wait out short 429
    rate-limit windows (per-minute token budgets).
    """

    transport_failures = 0
    rate_limit_waits = 0

    while True:
        try:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
        except httpx.TransportError:
            transport_failures += 1

            if transport_failures >= attempts:
                raise

            await asyncio.sleep(2)
            continue

        if response.status_code != 429 or rate_limit_waits >= RATE_LIMIT_RETRIES:
            return response

        wait = _retry_after_seconds(response)

        if wait is None or wait > MAX_RATE_LIMIT_WAIT:
            return response

        rate_limit_waits += 1
        print(f"[LLM] Rate limited; waiting {wait + 1:.0f}s")
        await asyncio.sleep(wait + 1)


async def chat_json(
    messages: list[dict[str, str]],
    tier: Tier = "fast",
    max_tokens: int = 2000,
    temperature: float = 0.1,
) -> tuple[Any, str]:
    """
    Run a chat completion and parse JSON from the reply.

    Returns (parsed_json, "provider:model"). Raises
    LLMUnavailable if every provider in the chain fails.
    """

    chain = build_chain(tier)

    if not chain:
        raise LLMUnavailable(
            "No LLM provider configured "
            "(set GROQ_API_KEY, GEMINI_API_KEY, ... or HF_TOKEN)"
        )

    errors: list[str] = []

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(120.0, connect=10.0)
    ) as client:

        for provider, model in chain:
            if _cooldown.get(provider.name, 0) > time.monotonic():
                continue

            label = f"{provider.name}:{model}"

            request_messages = [dict(message) for message in messages]

            # Qwen3 thinks by default; triage doesn't need it.
            if "qwen3" in model.lower():
                request_messages[-1]["content"] += "\n\n/no_think"

            # One retry on malformed JSON, feeding the error back.
            for attempt in range(2):
                payload: dict[str, Any] = {
                    "model": model,
                    "messages": request_messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }

                if provider.json_mode:
                    payload["response_format"] = {"type": "json_object"}

                # gpt-oss reasons before answering; its hidden
                # reasoning tokens count against max_tokens.
                if "gpt-oss" in model:
                    payload["reasoning_effort"] = "low"

                try:
                    response = await _post_with_retry(
                        client,
                        f"{provider.base_url}/chat/completions",
                        provider.api_key,
                        payload,
                    )
                    response.raise_for_status()

                    content = (
                        response.json()["choices"][0]["message"].get("content")
                        or ""
                    )

                except (httpx.HTTPError, KeyError, ValueError) as error:
                    status = (
                        error.response.status_code
                        if isinstance(error, httpx.HTTPStatusError)
                        else type(error).__name__
                    )
                    errors.append(f"{label}: {status}")
                    print(f"[LLM] {label} failed ({status}); trying next provider")
                    _cooldown[provider.name] = time.monotonic() + COOLDOWN_SECONDS
                    break

                try:
                    return extract_json(content), label

                except (ValueError, json.JSONDecodeError) as error:
                    errors.append(f"{label}: bad JSON ({error})")

                    if attempt == 0:
                        request_messages = request_messages + [
                            {"role": "assistant", "content": content[:4000]},
                            {
                                "role": "user",
                                "content": (
                                    f"That was not valid JSON ({error}). "
                                    "Reply again with ONLY the JSON."
                                ),
                            },
                        ]

    raise LLMUnavailable(
        "All LLM providers failed: "
        + ("; ".join(errors) or "all are cooling down after earlier errors")
    )
