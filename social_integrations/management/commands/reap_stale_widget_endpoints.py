"""Operator-facing wrapper around the widget-endpoint reaper Celery task.

Useful when debugging a stuck widget visitor row — run with ``--dry-run``
first to confirm what would be deleted, then re-run without the flag to
actually tombstone the PJSIP rows.

Usage::

    python manage.py reap_stale_widget_endpoints --dry-run
    python manage.py reap_stale_widget_endpoints
"""
from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Sweep PJSIP realtime rows for widget visitor sessions whose "
        "ephemeral SIP creds (4h TTL) have gone stale. Mirrors the "
        "hourly Celery beat task 'social_integrations.reap_stale_widget_endpoints'."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Log what would be deleted without actually tombstoning rows.',
        )

    def handle(self, *args, **options):
        from social_integrations.tasks import _reap_widget_endpoints

        dry_run = options.get('dry_run', False)
        reaped = _reap_widget_endpoints(dry_run=dry_run)
        total = sum(len(v) for v in reaped.values())

        if not reaped:
            self.stdout.write(self.style.SUCCESS(
                'No stale widget endpoints found.'
            ))
            return

        for tenant_schema, session_ids in reaped.items():
            prefix = '[DRY RUN] Would reap' if dry_run else 'Reaped'
            for session_id in session_ids:
                self.stdout.write(
                    f'  {prefix} tenant={tenant_schema} session={session_id}'
                )

        summary = (
            f'{total} stale widget endpoint(s) across {len(reaped)} tenant(s).'
        )
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'[DRY RUN] {summary} Nothing was deleted.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(summary))
