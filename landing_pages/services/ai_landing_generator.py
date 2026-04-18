"""Claude API wrapper for landing-page drafting.

Uses Anthropic's **tool use** pattern: we define a strict JSON schema for
the landing-page payload and force Claude to respond via a tool call.
Anthropic's server validates the schema for us, so we never have to
parse multi-kilobyte JSON strings that might have unescaped newlines,
quotes, or other whitespace hiccups inside content blocks.

Callers (the management command) handle persistence, retries, and
status transitions on LandingTopic / LandingPage. This module only
talks to Claude and surfaces a typed payload.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.conf import settings

from .prompt_templates import SYSTEM_PROMPT, build_user_prompt

if TYPE_CHECKING:
    from landing_pages.models import LandingTopic


logger = logging.getLogger(__name__)


# JSON schema for the tool Claude must call. Anthropic validates this
# on the server and returns a parsed dict in `tool_use_block.input`.
LANDING_PAGE_TOOL = {
    "name": "save_landing_page",
    "description": (
        "Save the drafted landing page. Must be called with the full "
        "bilingual payload matching the EchoDesk brief."
    ),
    "input_schema": {
        "type": "object",
        "required": [
            "title_ka", "title_en",
            "hero_subtitle_ka", "hero_subtitle_en",
            "summary_ka", "summary_en",
            "meta_title_ka", "meta_title_en",
            "meta_description_ka", "meta_description_en",
            "keywords",
            "og_tag",
            "content_blocks",
            "faq_items",
        ],
        "properties": {
            "title_ka": {"type": "string", "minLength": 1, "maxLength": 120},
            "title_en": {"type": "string", "minLength": 1, "maxLength": 120},
            "hero_subtitle_ka": {"type": "string", "minLength": 1, "maxLength": 300},
            "hero_subtitle_en": {"type": "string", "minLength": 1, "maxLength": 300},
            "summary_ka": {"type": "string", "minLength": 1, "maxLength": 300},
            "summary_en": {"type": "string", "minLength": 1, "maxLength": 300},
            "meta_title_ka": {"type": "string", "minLength": 1, "maxLength": 120},
            "meta_title_en": {"type": "string", "minLength": 1, "maxLength": 120},
            "meta_description_ka": {"type": "string", "minLength": 1, "maxLength": 300},
            "meta_description_en": {"type": "string", "minLength": 1, "maxLength": 300},
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 3,
                "maxItems": 15,
            },
            "og_tag": {"type": "string", "minLength": 1, "maxLength": 40},
            "content_blocks": {
                "type": "array",
                "minItems": 3,
                "maxItems": 8,
                "items": {
                    "oneOf": [
                        {
                            "type": "object",
                            "required": ["type", "heading_ka", "heading_en", "items"],
                            "properties": {
                                "type": {"const": "benefit_grid"},
                                "heading_ka": {"type": "string", "minLength": 1},
                                "heading_en": {"type": "string", "minLength": 1},
                                "items": {
                                    "type": "array",
                                    "minItems": 3,
                                    "maxItems": 6,
                                    "items": {
                                        "type": "object",
                                        "required": [
                                            "icon", "title_ka", "title_en",
                                            "description_ka", "description_en",
                                        ],
                                        "properties": {
                                            "icon": {"type": "string"},
                                            "title_ka": {"type": "string"},
                                            "title_en": {"type": "string"},
                                            "description_ka": {"type": "string"},
                                            "description_en": {"type": "string"},
                                        },
                                    },
                                },
                            },
                        },
                        {
                            "type": "object",
                            "required": ["type", "heading_ka", "heading_en", "items"],
                            "properties": {
                                "type": {"const": "checklist"},
                                "heading_ka": {"type": "string"},
                                "heading_en": {"type": "string"},
                                "items": {
                                    "type": "array",
                                    "minItems": 3,
                                    "maxItems": 10,
                                    "items": {
                                        "type": "object",
                                        "required": ["text_ka", "text_en"],
                                        "properties": {
                                            "text_ka": {"type": "string"},
                                            "text_en": {"type": "string"},
                                        },
                                    },
                                },
                            },
                        },
                        {
                            "type": "object",
                            "required": [
                                "type", "heading_ka", "heading_en",
                                "feature_slug", "body_ka", "body_en",
                            ],
                            "properties": {
                                "type": {"const": "feature_showcase"},
                                "heading_ka": {"type": "string"},
                                "heading_en": {"type": "string"},
                                "feature_slug": {"type": "string"},
                                "body_ka": {"type": "string", "minLength": 50},
                                "body_en": {"type": "string", "minLength": 50},
                            },
                        },
                    ],
                },
            },
            "faq_items": {
                "type": "array",
                "minItems": 3,
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "required": [
                        "question_ka", "question_en",
                        "answer_ka", "answer_en",
                    ],
                    "properties": {
                        "question_ka": {"type": "string"},
                        "question_en": {"type": "string"},
                        "answer_ka": {"type": "string"},
                        "answer_en": {"type": "string"},
                    },
                },
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
    # prompt drift — persisted on LandingPageRun.
    raw_preview: str


def generate_landing_page(topic: "LandingTopic") -> GenerationResult:
    """Draft one landing page via Claude tool use. Raises on failure."""
    if not settings.ANTHROPIC_API_KEY:
        raise AIGenerationError(
            "ANTHROPIC_API_KEY is not set. Add it to environment to run "
            "landing-page generation."
        )

    # Import lazily so the app boots without anthropic installed in
    # environments that don't run the landing-page task.
    from anthropic import Anthropic

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    model = settings.BLOG_AI_MODEL
    user_prompt = build_user_prompt(topic)

    logger.info("landing.ai: calling Claude model=%s topic=%s", model, topic.slug)

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        tools=[LANDING_PAGE_TOOL],
        tool_choice={"type": "tool", "name": "save_landing_page"},
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
    """Pull the ``save_landing_page`` tool call out of Claude's response.

    Anthropic returns a list of content blocks; we expect exactly one
    tool_use block with ``name='save_landing_page'``.
    """
    blocks = response.content or []
    tool_block = None
    text_fragments: list[str] = []

    for block in blocks:
        btype = getattr(block, "type", None)
        if btype == "tool_use" and getattr(block, "name", "") == "save_landing_page":
            tool_block = block
        elif btype == "text":
            text_fragments.append(getattr(block, "text", "") or "")

    preview = ("\n".join(text_fragments))[:4000] if text_fragments else ""

    if tool_block is None:
        raise AIGenerationError(
            "Claude did not call the save_landing_page tool. "
            f"Got {len(blocks)} content block(s), "
            f"types={[getattr(b, 'type', '?') for b in blocks]}"
        )

    payload = getattr(tool_block, "input", None)
    if not isinstance(payload, dict):
        raise AIGenerationError("tool_use.input was not a dict.")

    return payload, preview
