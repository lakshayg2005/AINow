"""
Free-tier LLM access with provider fallback, built on LangChain
(`ChatOpenAI` talking to each provider's OpenAI-compatible
endpoint).

Providers are tried in order; a provider that rate-limits or
errors is skipped for the rest of the process.

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
from langchain_core.exceptions import ModelConnectionError, ModelError, ModelRateLimitError, ModelTimeoutError
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

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
TRANSPORT_RETRIES = 3

_RETRY_IN = re.compile(r"try again in (?:(\d+)m)?([\d.]+)s", re.IGNORECASE)


def _retry_after_seconds(
    error: ModelRateLimitError,
) -> float | None:
    response = getattr(error, "response", None)

    if response is not None:
        header = response.headers.get("retry-after")

        if header:
            try:
                return float(header)
            except ValueError:
                pass

    match = _RETRY_IN.search(str(error))

    if match:
        return int(match.group(1) or 0) * 60 + float(match.group(2))

    return None


def _error_label(
    error: Exception,
) -> str:
    status = getattr(error, "status_code", None)
    return str(status) if status is not None else type(error).__name__


def _build_model(
    provider: Provider,
    model_name: str,
    max_tokens: int,
    temperature: float,
) -> ChatOpenAI:
    model_kwargs: dict[str, Any] = {}
    extra_body: dict[str, Any] = {}

    if provider.json_mode:
        model_kwargs["response_format"] = {"type": "json_object"}

    # gpt-oss reasons before answering; its hidden reasoning
    # tokens count against max_tokens. Sent via extra_body (a
    # raw body passthrough) since it's a Groq-specific field the
    # OpenAI client doesn't know about.
    if "gpt-oss" in model_name:
        extra_body["reasoning_effort"] = "low"

    return ChatOpenAI(
        base_url=provider.base_url,
        api_key=provider.api_key,
        model=model_name,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=httpx.Timeout(120.0, connect=10.0),
        max_retries=0,  # we own retry/backoff below
        model_kwargs=model_kwargs,
        extra_body=extra_body or None,
    )


def _to_lc_messages(
    messages: list[dict[str, str]],
    model_name: str,
) -> list[BaseMessage]:
    last_index = len(messages) - 1
    lc_messages: list[BaseMessage] = []

    for index, message in enumerate(messages):
        content = message["content"]

        # Qwen3 thinks by default; triage doesn't need it.
        if index == last_index and "qwen3" in model_name.lower():
            content += "\n\n/no_think"

        lc_messages.append(
            SystemMessage(content=content)
            if message["role"] == "system"
            else HumanMessage(content=content)
        )

    return lc_messages


async def _invoke_with_retry(
    model: ChatOpenAI,
    messages: list[BaseMessage],
) -> AIMessage:
    """
    Retry dropped connections, and wait out short 429
    rate-limit windows (per-minute token budgets).
    """

    transport_failures = 0
    rate_limit_waits = 0

    while True:
        try:
            return await model.ainvoke(messages)

        except (ModelConnectionError, ModelTimeoutError):
            transport_failures += 1

            if transport_failures >= TRANSPORT_RETRIES:
                raise

            await asyncio.sleep(2)

        except ModelRateLimitError as error:
            wait = _retry_after_seconds(error)

            if (
                wait is None
                or wait > MAX_RATE_LIMIT_WAIT
                or rate_limit_waits >= RATE_LIMIT_RETRIES
            ):
                raise

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

    for provider, model_name in chain:
        if _cooldown.get(provider.name, 0) > time.monotonic():
            continue

        label = f"{provider.name}:{model_name}"
        model = _build_model(provider, model_name, max_tokens, temperature)
        lc_messages = _to_lc_messages(messages, model_name)

        # One retry on malformed JSON, feeding the error back.
        for attempt in range(2):
            try:
                reply = await _invoke_with_retry(model, lc_messages)
                content = reply.content or ""

            except (ModelError, httpx.HTTPError) as error:
                status = _error_label(error)
                errors.append(f"{label}: {status}")
                print(f"[LLM] {label} failed ({status}); trying next provider")
                _cooldown[provider.name] = time.monotonic() + COOLDOWN_SECONDS
                break

            try:
                return extract_json(content), label

            except (ValueError, json.JSONDecodeError) as error:
                errors.append(f"{label}: bad JSON ({error})")

                if attempt == 0:
                    lc_messages = lc_messages + [
                        AIMessage(content=str(content)[:4000]),
                        HumanMessage(
                            content=(
                                f"That was not valid JSON ({error}). "
                                "Reply again with ONLY the JSON."
                            )
                        ),
                    ]

    raise LLMUnavailable(
        "All LLM providers failed: "
        + ("; ".join(errors) or "all are cooling down after earlier errors")
    )
