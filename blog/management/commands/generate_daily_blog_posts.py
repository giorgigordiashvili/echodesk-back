"""Daily blog-post generator.

Picks the top-N ``pending`` BlogTopic rows by priority and asks Claude
to draft a BlogPost for each. Drafts land in ``status='review'`` —
nothing is auto-published. Editors approve via the Django admin.

Usage::

    python manage.py generate_daily_blog_posts                       # default limit
    python manage.py generate_daily_blog_posts --limit=3
    python manage.py generate_daily_blog_posts --topic-slug=kommo-vs-echodesk
    python manage.py generate_daily_blog_posts --dry-run             # no writes
"""

from __future__ import annotations

import json
import traceback

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from blog.models import BlogPost, BlogPostRun, BlogTopic
from blog.services.ai_post_generator import (
    AIGenerationError,
    GenerationResult,
    generate_blog_post,
)


MAX_RETRIES = 3  # per topic before we park it as 'skipped'


class Command(BaseCommand):
    help = "Draft blog posts for pending BlogTopics via Claude."

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
            topics = list(BlogTopic.objects.filter(slug=topic_slug))
            if not topics:
                raise CommandError(f"No BlogTopic with slug {topic_slug!r}.")
        else:
            topics = list(
                BlogTopic.objects.filter(status="pending")
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

    def _draft_one(self, topic: BlogTopic, dry_run: bool) -> None:
        self.stdout.write(f"[{topic.slug}] drafting (type={topic.post_type})...")

        if not dry_run:
            # Mark drafting so a concurrent beat run doesn't double-pick it.
            BlogTopic.objects.filter(pk=topic.pk).update(status="drafting")

        run = BlogPostRun(topic=topic, model=settings.BLOG_AI_MODEL)
        run.save()  # timestamp via auto_now_add

        try:
            result = generate_blog_post(topic)
        except AIGenerationError as exc:
            run.completed_at = timezone.now()
            run.error_message = str(exc)
            run.success = False
            if not dry_run:
                run.save()
                # Retry budget — return to pending until we hit MAX_RETRIES.
                BlogTopic.objects.filter(pk=topic.pk).update(
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

        with transaction.atomic():
            post = _persist_post(topic, result)
            run.resulting_post = post
            run.save()
            BlogTopic.objects.filter(pk=topic.pk).update(
                status="drafted",
                processed_at=timezone.now(),
                generated_post_id=post.pk,
                updated_at=timezone.now(),
            )

        self.stdout.write(self.style.SUCCESS(
            f"[{topic.slug}] saved post id={post.pk} "
            f"(tokens: prompt={result.prompt_tokens}, out={result.completion_tokens})"
        ))


def _safe_store_response(result: GenerationResult) -> dict:
    """Store a truncated copy of the raw response in BlogPostRun — useful
    for debugging prompt drift without blowing out the DB row size."""
    text = result.raw_response_text or ""
    return {
        "text_preview": text[:4000],
        "text_length": len(text),
        "model": result.model,
    }


def _persist_post(topic: BlogTopic, result: GenerationResult) -> BlogPost:
    p = result.payload
    post = BlogPost.objects.create(
        slug=_generate_unique_slug(topic.slug),
        post_type=topic.post_type,
        competitor_name=topic.competitor_name,
        title={"en": p["title_en"], "ka": p["title_ka"]},
        summary={"en": p["summary_en"], "ka": p["summary_ka"]},
        content_html={"en": p["content_en_html"], "ka": p["content_ka_html"]},
        meta_title={"en": p["meta_title_en"], "ka": p["meta_title_ka"]},
        meta_description={"en": p["meta_description_en"], "ka": p["meta_description_ka"]},
        keywords=p.get("keywords", []),
        faq_items=p.get("faq_items", []),
        status="review",
        source_topic=topic,
        generated_by_ai=True,
        ai_model=result.model,
        ai_prompt_tokens=result.prompt_tokens,
        ai_completion_tokens=result.completion_tokens,
        ai_generated_at=timezone.now(),
    )
    return post


def _generate_unique_slug(base: str) -> str:
    """If the topic slug already has a post attached, append a short
    counter. Human editors can rename later in the admin."""
    candidate = base
    suffix = 2
    while BlogPost.objects.filter(slug=candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate
