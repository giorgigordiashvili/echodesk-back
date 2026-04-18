"""Management command: kick off ``rebuild_tenant_asterisk_state`` synchronously.

Usage::

    # Single tenant
    python manage.py sync_tenant_asterisk acme

    # Every tenant (skips public)
    python manage.py sync_tenant_asterisk --all

Intended use cases:

* Initial provisioning of a fresh ``asterisk_state`` DB.
* Recovery after a sync failure batch (CLI is cheaper than a Celery roundtrip).
* Smoke testing while building the sync layer.

The command runs the task synchronously (via ``.apply()``) so you get the
summary in stdout immediately and don't need a worker online.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from crm.tasks import rebuild_tenant_asterisk_state


class Command(BaseCommand):
    help = "Resync a tenant's PBX state into the Asterisk realtime DB."

    def add_arguments(self, parser):
        parser.add_argument(
            "schema_name",
            nargs="?",
            help="Tenant schema name to resync (omit when using --all).",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            dest="all_tenants",
            help="Iterate every tenant (skipping the public schema).",
        )

    def handle(self, *args, **options):
        schema_name = options.get("schema_name")
        all_tenants = options.get("all_tenants", False)

        if not schema_name and not all_tenants:
            raise CommandError(
                "Pass a schema_name or --all. Run `--help` for usage."
            )
        if schema_name and all_tenants:
            raise CommandError("Pass either a schema_name or --all, not both.")

        if schema_name:
            self._resync_one(schema_name)
            return

        # --all: pick up every tenant except the public schema.
        from tenants.models import Tenant

        for tenant in Tenant.objects.exclude(schema_name="public"):
            self._resync_one(tenant.schema_name)

    def _resync_one(self, schema_name: str) -> None:
        self.stdout.write(f"Resyncing Asterisk state for tenant={schema_name}...")
        # Run the task body in-process so we get the summary immediately.
        summary = rebuild_tenant_asterisk_state.apply(
            args=[schema_name]
        ).get(disable_sync_subtasks=False)
        self.stdout.write(self.style.SUCCESS(f"  done: {summary}"))
