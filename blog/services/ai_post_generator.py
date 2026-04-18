"""Claude API wrapper for blog-post drafting.

Thin layer on top of the `anthropic` SDK — it handles system+user
prompt assembly, JSON schema validation of the response, and bubbles
the token counts up so the caller can persist them for audit.

Callers (the management command) are responsible for persistence,
retries, and status transitions on BlogTopic / BlogPost. This module
just talks to Claude.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.conf import settings

from .prompt_templates import SYSTEM_PROMPT, build_user_prompt

if TYPE_CHECKING:
    from blog.models import BlogTopic


logger = logging.getLogger(__name__)


REQUIRED_KEYS = {
    "title_ka", "title_en",
    "summary_ka", "summary_en",
    "content_ka_html", "content_en_html",
    "meta_title_ka", "meta_title_en",
    "meta_description_ka", "meta_description_en",
    "faq_items",
    "keywords",
}

FAQ_ITEM_REQUIRED_KEYS = {"question_ka", "question_en", "answer_ka", "answer_en"}


class AIGenerationError(RuntimeError):
    """Raised when Claude's response can't be parsed or is missing fields."""


@dataclass
class GenerationResult:
    """Structured result of a successful Claude call."""

    payload: dict[str, Any]
    prompt_tokens: int
    completion_tokens: int
    model: str
    raw_response_text: str


def generate_blog_post(topic: "BlogTopic") -> GenerationResult:
    """Ask Claude to draft a blog post for this topic.

    Raises ``AIGenerationError`` on missing key / invalid JSON / API failure.
    Caller decides retry/backoff policy.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise AIGenerationError(
            "ANTHROPIC_API_KEY is not set. Add it to environment to run blog "
            "generation."
        )

    # Import lazily so the app boots even if anthropic isn't installed in
    # environments that don't run the blog task.
    from anthropic import Anthropic

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    model = settings.BLOG_AI_MODEL
    user_prompt = build_user_prompt(topic)

    logger.info("blog.ai: calling Claude model=%s topic=%s", model, topic.slug)

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Claude's response.content is a list of blocks; for text-only responses
    # the payload is in the first block.
    blocks = response.content or []
    text = ""
    for block in blocks:
        # SDK exposes blocks as objects with .type / .text attributes.
        text += getattr(block, "text", "") or ""
    text = text.strip()

    payload = _parse_json_strict(text)
    _validate_schema(payload)

    return GenerationResult(
        payload=payload,
        prompt_tokens=getattr(response.usage, "input_tokens", 0),
        completion_tokens=getattr(response.usage, "output_tokens", 0),
        model=model,
        raw_response_text=text,
    )


def _parse_json_strict(text: str) -> dict[str, Any]:
    """Claude is instructed to return bare JSON, but occasionally wraps it in
    markdown fences anyway. Strip fences, then parse."""
    if not text:
        raise AIGenerationError("Empty response from Claude.")

    # Strip ```json ... ``` or ``` ... ``` if present.
    fence = re.match(r"^```(?:json)?\s*(.+?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise AIGenerationError(f"Claude did not return valid JSON: {e}") from e


def _validate_schema(payload: dict[str, Any]) -> None:
    """Sanity-check the shape before we try to persist."""
    missing = REQUIRED_KEYS - set(payload.keys())
    if missing:
        raise AIGenerationError(f"Claude response missing required keys: {sorted(missing)}")

    # Basic type checks — enough to catch obvious drift, not full JSON-schema.
    for k in (
        "title_ka", "title_en", "summary_ka", "summary_en",
        "content_ka_html", "content_en_html",
        "meta_title_ka", "meta_title_en",
        "meta_description_ka", "meta_description_en",
    ):
        if not isinstance(payload.get(k), str) or not payload[k].strip():
            raise AIGenerationError(f"Field {k!r} must be a non-empty string.")

    faq_items = payload.get("faq_items")
    if not isinstance(faq_items, list) or len(faq_items) < 3:
        raise AIGenerationError("faq_items must be a list with at least 3 entries.")
    for idx, item in enumerate(faq_items):
        if not isinstance(item, dict):
            raise AIGenerationError(f"faq_items[{idx}] must be an object.")
        missing = FAQ_ITEM_REQUIRED_KEYS - set(item.keys())
        if missing:
            raise AIGenerationError(f"faq_items[{idx}] missing keys: {sorted(missing)}")

    keywords = payload.get("keywords")
    if not isinstance(keywords, list):
        raise AIGenerationError("keywords must be a list.")
