"""LLM provider layer.

Three interchangeable backends selected by settings.LLM_PROVIDER:

- "demo" (default): no external API at all. Streams a canned answer built from
  the retrieved excerpts, so the full RAG pipeline (embed -> search -> rank ->
  cite) still runs and the UI behaves exactly like production. Zero cost.
- "groq": Groq's OpenAI-compatible API. Has a free tier that requires no
  payment method, so it can never bill anything.
- "anthropic": Claude via the Anthropic SDK. Paid per token.

`validate_provider_config()` runs at startup so a misconfigured provider fails
fast instead of erroring on the first chat message.
"""

import json
import time
from collections.abc import Iterator
from functools import lru_cache

import httpx

from app.core.config import settings

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

_DEMO_TOKEN_DELAY_SECONDS = 0.015  # small delay so streaming is visible in the UI


class ProviderConfigError(RuntimeError):
    pass


def validate_provider_config() -> None:
    provider = settings.LLM_PROVIDER.lower()
    if provider == "demo":
        return
    if provider == "groq":
        if not settings.GROQ_API_KEY:
            raise ProviderConfigError("LLM_PROVIDER=groq requires GROQ_API_KEY to be set")
        return
    if provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise ProviderConfigError(
                "LLM_PROVIDER=anthropic requires ANTHROPIC_API_KEY to be set"
            )
        return
    raise ProviderConfigError(
        f"Unknown LLM_PROVIDER '{settings.LLM_PROVIDER}'. Use 'demo', 'groq', or 'anthropic'."
    )


def stream_chat(
    system: str, messages: list[dict], hits: list[dict] | None = None
) -> Iterator[str]:
    """Yield response text deltas for the given conversation.

    `hits` (the retrieved chunks) are only used by the demo provider to build
    a grounded-looking canned answer; real providers get them via `system`.
    """
    provider = settings.LLM_PROVIDER.lower()
    if provider == "groq":
        return _stream_groq(system, messages)
    if provider == "anthropic":
        return _stream_anthropic(system, messages)
    return _stream_demo(messages, hits or [])


# ---- demo ----


def _stream_demo(messages: list[dict], hits: list[dict]) -> Iterator[str]:
    question = messages[-1]["content"] if messages else ""
    parts: list[str] = [
        "**Demo mode** — no LLM is connected (`LLM_PROVIDER=demo`), so this reply is "
        "generated locally at zero cost. Everything else is real: your question was "
        "embedded, the vector store was searched, and the excerpts below were retrieved "
        "and ranked for relevance.\n\n"
    ]
    if hits:
        parts.append(f'For **"{question[:120]}"**, the most relevant passages found were:\n\n')
        for i, hit in enumerate(hits[:3], start=1):
            snippet = " ".join(hit["text"].split())[:220]
            parts.append(f'[{i}] From *{hit["filename"]}*: "{snippet}…"\n\n')
        parts.append(
            "With a live model these passages would be synthesized into a direct, "
            "cited answer. "
        )
    else:
        parts.append(
            "No relevant passages were found in your indexed documents for this "
            "question — try uploading a related document or rephrasing. "
        )
    parts.append(
        "To enable real answers, set `LLM_PROVIDER=groq` (free tier, no card required) "
        "or `LLM_PROVIDER=anthropic` in your `.env`."
    )

    for word in "".join(parts).split(" "):
        yield word + " "
        time.sleep(_DEMO_TOKEN_DELAY_SECONDS)


# ---- groq (OpenAI-compatible) ----


def _stream_groq(system: str, messages: list[dict]) -> Iterator[str]:
    payload = {
        "model": settings.GROQ_MODEL,
        "max_tokens": settings.LLM_MAX_TOKENS,
        "stream": True,
        "messages": [{"role": "system", "content": system}, *messages],
    }
    headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}
    with (
        httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client,
        client.stream("POST", GROQ_API_URL, headers=headers, json=payload) as response,
    ):
        if response.status_code != 200:
            response.read()
            raise RuntimeError(f"Groq API returned {response.status_code}")
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            data = line.removeprefix("data: ")
            if data == "[DONE]":
                break
            delta = json.loads(data)["choices"][0].get("delta", {})
            if content := delta.get("content"):
                yield content


# ---- anthropic ----


@lru_cache
def _get_anthropic_client():
    import anthropic

    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def _stream_anthropic(system: str, messages: list[dict]) -> Iterator[str]:
    # Streaming keeps time-to-first-token low; adaptive thinking lets the model
    # decide when a question needs deeper reasoning.
    client = _get_anthropic_client()
    with client.messages.stream(
        model=settings.LLM_MODEL,
        max_tokens=settings.LLM_MAX_TOKENS,
        thinking={"type": "adaptive"},
        system=system,
        messages=messages,
    ) as stream:
        yield from stream.text_stream
