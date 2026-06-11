"""Anthropic client wrapper.

Streaming keeps time-to-first-token low for the chat UI, and adaptive thinking
lets the model decide when a question needs deeper reasoning.
"""

from collections.abc import Iterator
from functools import lru_cache

import anthropic

from app.core.config import settings


@lru_cache
def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def stream_chat(system: str, messages: list[dict]) -> Iterator[str]:
    """Yield response text deltas for the given conversation."""
    client = get_client()
    with client.messages.stream(
        model=settings.LLM_MODEL,
        max_tokens=settings.LLM_MAX_TOKENS,
        thinking={"type": "adaptive"},
        system=system,
        messages=messages,
    ) as stream:
        yield from stream.text_stream
