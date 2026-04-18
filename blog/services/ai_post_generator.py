"""Claude API wrapper for blog-post drafting.

Uses Anthropic's **tool use** pattern: we define a strict JSON schema for
the blog-post payload and force Claude to respond via a tool call.
Anthropic's server validates the schema for us, so we never have to
parse a multi-thousand-character JSON string that might have unescaped
newlines, quotes, or other whitespace hiccups inside long HTML content.

Callers (the management command) handle persistence, retries, and
status transitions on BlogTopic / BlogPost. This module only talks to
Claude and surfaces a typed payload.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.conf import settings

from .prompt_templates import SYSTEM_PROMPT, build_user_prompt

if TYPE_CHECKING:
    from blog.models import BlogTopic


logger = logging.getLogger(__name__)


# JSON schema for the tool Claude must call. Anthropic validates this
# on the server and returns a parsed dict in `tool_use_block.input`.
BLOG_POST_TOOL = {
    "name": "save_blog_post",
    "description": (
        "Save the drafted blog post. Must be called with the full bilingual "
        "content and metadata matching the EchoDesk brief."
    ),
    "input_schema": {
        "type": "object",
        "required": [
            "title_ka", "title_en",
            "summary_ka", "summary_en",
            "content_ka_html", "content_en_html",
            "meta_title_ka", "meta_title_en",
            "meta_description_ka", "meta_description_en",
            "faq_items", "keywords",
        ],
        "properties": {
            "title_ka": {"type": "string", "minLength": 1, "maxLength": 120},
            "title_en": {"type": "string", "minLength": 1, "maxLength": 120},
            "summary_ka": {"type": "string", "minLength": 1, "maxLength": 300},
            "summary_en": {"type": "string", "minLength": 1, "maxLength": 300},
            "content_ka_html": {"type": "string", "minLength": 200},
            "content_en_html": {"type": "string", "minLength": 200},
            "meta_title_ka": {"type": "string", "minLength": 1, "maxLength": 120},
            "meta_title_en": {"type": "string", "minLength": 1, "maxLength": 120},
            "meta_description_ka": {"type": "string", "minLength": 1, "maxLength": 300},
            "meta_description_en": {"type": "string", "minLength": 1, "maxLength": 300},
            "faq_items": {
                "type": "array",
                "minItems": 3,
                "maxItems": 10,
                "items": {
                    "type": "object",
                    "required": ["question_ka", "question_en", "answer_ka", "answer_en"],
                    "properties": {
                        "question_ka": {"type": "string", "minLength": 1},
                        "question_en": {"type": "string", "minLength": 1},
                        "answer_ka": {"type": "string", "minLength": 1},
                        "answer_en": {"type": "string", "minLength": 1},
                    },
                },
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
        },
    },
}


class AIGenerationError(RuntimeError):
    """Raised when Claude's response can't be interpreted (no tool call,
    missing fields, API error). Caller decides retry behaviour."""


@dataclass
class GenerationResult:
    payload: dict[str, Any]
    prompt_tokens: int
    completion_tokens: int
    model: str
    # Preview of what Claude returned (truncated). Useful for debugging
    # prompt drift — persisted on BlogPostRun.
    raw_preview: str


def generate_blog_post(topic: "BlogTopic") -> GenerationResult:
    """Draft one blog post via Claude tool use. Raises on failure."""
    if not settings.ANTHROPIC_API_KEY:
        raise AIGenerationError(
            "ANTHROPIC_API_KEY is not set. Add it to environment to run blog generation."
        )

    # Import lazily so app boots without anthropic installed in environments
    # that don't run the blog task.
    from anthropic import Anthropic

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    model = settings.BLOG_AI_MODEL
    user_prompt = build_user_prompt(topic)

    logger.info("blog.ai: calling Claude model=%s topic=%s", model, topic.slug)

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        tools=[BLOG_POST_TOOL],
        tool_choice={"type": "tool", "name": "save_blog_post"},
        messages=[{"role": "user", "content": user_prompt}],
    )

    payload, preview = _extract_tool_payload(response)

    return GenerationResult(
        payload=payload,
        prompt_tokens=getattr(response.usage, "input_tokens", 0) or 0,
        completion_tokens=getattr(response.usage, "output_tokens", 0) or 0,
        model=model,
        raw_preview=preview,
    )


def _extract_tool_payload(response) -> tuple[dict[str, Any], str]:
    """Pull the ``save_blog_post`` tool call out of Claude's response.

    Anthropic returns a list of content blocks; we expect exactly one
    tool_use block with ``name='save_blog_post'``.
    """
    blocks = response.content or []
    tool_block = None
    text_fragments: list[str] = []

    for block in blocks:
        btype = getattr(block, "type", None)
        if btype == "tool_use" and getattr(block, "name", "") == "save_blog_post":
            tool_block = block
        elif btype == "text":
            text_fragments.append(getattr(block, "text", "") or "")

    preview = ("\n".join(text_fragments))[:4000] if text_fragments else ""

    if tool_block is None:
        raise AIGenerationError(
            "Claude did not call the save_blog_post tool. "
            f"Got {len(blocks)} content block(s), "
            f"types={[getattr(b, 'type', '?') for b in blocks]}"
        )

    payload = getattr(tool_block, "input", None)
    if not isinstance(payload, dict):
        raise AIGenerationError("tool_use.input was not a dict.")

    return payload, preview
