"""Daily landing-page generator.

Picks the top-N ``pending`` LandingTopic rows by priority and asks Claude
to draft a LandingPage for each. Drafts land in ``status='review'`` by
default; set ``LANDING_AUTO_PUBLISH=true`` to publish immediately with
``published_at=now()`` (no human approval step).

Usage::

    python manage.py generate_daily_landing_pages                              # default limit
    python manage.py generate_daily_landing_pages --limit=3
    python manage.py generate_daily_landing_pages --topic-slug=whatsapp-business-crm-georgia
    python manage.py generate_daily_landing_pages --dry-run                   # no writes
"""

from __future__ import annotations

import json
import traceback

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from landing_pages.models import LandingPage, LandingPageRun, LandingTopic
from landing_pages.services.ai_landing_generator import (
    AIGenerationError,
    GenerationResult,
    generate_landing_page,
)


MAX_RETRIES = 3  # per topic before we park it as 'skipped'


class Command(BaseCommand):
    help = "Draft landing pages for pending LandingTopics via Claude."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit", type=int, default=None,
            help="Max topics to draft in this run (defaults to BLOG_DAILY_POST_LIMIT).",
        )
        parser.add_argument(
            "--topic-slug", type=str, default=None,
            help="Draft a specific topic by slug (ignores queue order).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Call Claude and print the response, but don't persist.",
        )

    def handle(self, *args, **options):
        limit = options["limit"] or settings.BLOG_DAILY_POST_LIMIT
        dry_run = options["dry_run"]
        topic_slug = options["topic_slug"]

        if topic_slug:
            topics = list(LandingTopic.objects.filter(slug=topic_slug))
            if not topics:
                raise CommandError(f"No LandingTopic with slug {topic_slug!r}.")
        else:
            topics = list(
                LandingTopic.objects.filter(status="pending")
                .order_by("-priority", "created_at")[:limit]
            )

        if not topics:
            self.stdout.write(self.style.WARNING("No pending topics — nothing to draft."))
            return

        self.stdout.write(
            f"Drafting {len(topics)} topic(s){' [DRY RUN]' if dry_run else ''}..."
        )

        succeeded, failed = 0, 0
        for topic in topics:
            try:
                self._draft_one(topic, dry_run=dry_run)
                succeeded += 1
            except Exception as exc:  # noqa: BLE001 — we log everything, keep looping
                failed += 1
                self.stderr.write(self.style.ERROR(
                    f"[{topic.slug}] FAILED: {exc}"
                ))
                self.stderr.write(traceback.format_exc())

        self.stdout.write(self.style.SUCCESS(
            f"Done. succeeded={succeeded} failed={failed}"
        ))

    # ------------------------------------------------------------------

    def _draft_one(self, topic: LandingTopic, dry_run: bool) -> None:
        self.stdout.write(f"[{topic.slug}] drafting (type={topic.page_type})...")

        if not dry_run:
            # Mark drafting so a concurrent beat run doesn't double-pick it.
            LandingTopic.objects.filter(pk=topic.pk).update(status="drafting")

        run = LandingPageRun(topic=topic, model=settings.BLOG_AI_MODEL)
        run.save()  # timestamp via auto_now_add

        try:
            result = generate_landing_page(topic)
        except AIGenerationError as exc:
            run.completed_at = timezone.now()
            run.error_message = str(exc)
            run.success = False
            if not dry_run:
                run.save()
                # Retry budget — return to pending until we hit MAX_RETRIES.
                LandingTopic.objects.filter(pk=topic.pk).update(
                    retry_count=topic.retry_count + 1,
                    status=("skipped" if topic.retry_count + 1 >= MAX_RETRIES else "pending"),
                    updated_at=timezone.now(),
                )
            raise

        run.prompt_tokens = result.prompt_tokens
        run.completion_tokens = result.completion_tokens
        run.raw_response = _safe_store_response(result)
        run.completed_at = timezone.now()
        run.success = True

        if dry_run:
            self.stdout.write(self.style.NOTICE("DRY RUN — response:"))
            self.stdout.write(json.dumps(result.payload, indent=2, ensure_ascii=False))
            return

        auto_publish = bool(getattr(settings, "LANDING_AUTO_PUBLISH", False))

        with transaction.atomic():
            page = _persist_page(topic, result, auto_publish=auto_publish)
            run.resulting_page = page
            run.save()
            LandingTopic.objects.filter(pk=topic.pk).update(
                status=("published" if auto_publish else "drafted"),
                processed_at=timezone.now(),
                generated_page_id=page.pk,
                updated_at=timezone.now(),
            )

        self.stdout.write(self.style.SUCCESS(
            f"[{topic.slug}] saved page id={page.pk} status={page.status} "
            f"(tokens: prompt={result.prompt_tokens}, out={result.completion_tokens})"
        ))


def _safe_store_response(result: GenerationResult) -> dict:
    """Store a truncated copy of the tool-use response in LandingPageRun —
    useful for debugging prompt drift. We keep the structured payload keys
    plus any commentary Claude emitted alongside the tool call."""
    return {
        "preview": result.raw_preview[:4000],
        "model": result.model,
        "keys_present": sorted(result.payload.keys()) if result.payload else [],
    }


def _persist_page(
    topic: LandingTopic,
    result: GenerationResult,
    *,
    auto_publish: bool = False,
) -> LandingPage:
    p = result.payload
    now = timezone.now()
    page = LandingPage.objects.create(
        slug=_generate_unique_slug(topic.slug),
        page_type=topic.page_type,
        competitor_name=topic.competitor_name,
        title={"en": p["title_en"], "ka": p["title_ka"]},
        hero_subtitle={"en": p["hero_subtitle_en"], "ka": p["hero_subtitle_ka"]},
        summary={"en": p["summary_en"], "ka": p["summary_ka"]},
        meta_title={"en": p["meta_title_en"], "ka": p["meta_title_ka"]},
        meta_description={"en": p["meta_description_en"], "ka": p["meta_description_ka"]},
        keywords=p.get("keywords", []),
        og_tag=p.get("og_tag", ""),
        content_blocks=p.get("content_blocks", []),
        faq_items=p.get("faq_items", []),
        highlighted_feature_slugs=topic.highlighted_feature_slugs or [],
        status=("published" if auto_publish else "review"),
        published_at=(now if auto_publish else None),
        source_topic=topic,
        generated_by_ai=True,
        ai_model=result.model,
        ai_prompt_tokens=result.prompt_tokens,
        ai_completion_tokens=result.completion_tokens,
        ai_generated_at=now,
    )
    return page


def _generate_unique_slug(base: str) -> str:
    """If the topic slug already has a page attached, append a short
    counter. Human editors can rename later in the admin."""
    candidate = base
    suffix = 2
    while LandingPage.objects.filter(slug=candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate
