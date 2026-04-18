"""Celery tasks for the blog app."""

from io import StringIO

from celery import shared_task
from django.core.management import call_command


@shared_task(soft_time_limit=600, time_limit=900)
def generate_daily_blog_posts() -> str:
    """Wrapper around the ``generate_daily_blog_posts`` management command.

    Scheduled from CELERY_BEAT_SCHEDULE (daily 06:00 UTC). Drafts up to
    ``BLOG_DAILY_POST_LIMIT`` pending topics at a time. Soft limit of
    10 minutes is generous — each Claude call is ~20-60 seconds.
    """
    out = StringIO()
    call_command("generate_daily_blog_posts", stdout=out, stderr=out)
    return out.getvalue()
