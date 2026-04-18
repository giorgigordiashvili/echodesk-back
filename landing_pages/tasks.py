"""Celery tasks for the landing_pages app."""

from io import StringIO

from celery import shared_task
from django.core.management import call_command


@shared_task(soft_time_limit=600, time_limit=900)
def generate_daily_landing_pages() -> str:
    """Wrapper around the ``generate_daily_landing_pages`` management command.

    Scheduled from CELERY_BEAT_SCHEDULE (PR3 wires the beat entry; for PR1
    this task is invocable via the worker queue but not yet on the
    schedule). Drafts up to ``BLOG_DAILY_POST_LIMIT`` pending topics at a
    time. Soft limit of 10 minutes is generous — each Claude call is
    ~20-60 seconds.
    """
    out = StringIO()
    call_command("generate_daily_landing_pages", stdout=out, stderr=out)
    return out.getvalue()
