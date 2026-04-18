"""Apply Django migrations to the ``asterisk`` DB alias.

Why this exists: ``django-tenant-schemas`` replaces Django's native ``migrate``
command with a thin wrapper that only understands ``--shared`` / ``--tenant``
on the default DB and strips ``--database``. That makes it impossible to run
migrations against our secondary ``asterisk`` alias (which points at the
``asterisk_state`` Postgres schema) through the normal path.

This command shells out to a Python subprocess that invokes Django's native
migrate command directly, bypassing the tenant-schemas wrapper. Run it from
``build_production.sh`` on every deploy so realtime schema changes ship
without manual SQL.

Usage::

    python manage.py migrate_asterisk            # apply all pending
    python manage.py migrate_asterisk --plan     # show what would run
    python manage.py migrate_asterisk --fake     # record without executing
"""
from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Apply migrations to the asterisk DB alias (bypasses tenant-schemas)."

    def add_arguments(self, parser):
        parser.add_argument("--plan", action="store_true")
        parser.add_argument("--fake", action="store_true")
        parser.add_argument("--fake-initial", action="store_true")
        parser.add_argument("--run-syncdb", action="store_true")
        parser.add_argument(
            "migration_name",
            nargs="?",
            help="Specific migration to apply (default: all pending).",
        )

    def handle(self, *args, **opts):
        if not getattr(settings, "ASTERISK_SYNC_ENABLED", False):
            self.stdout.write(
                self.style.WARNING(
                    "ASTERISK_SYNC_ENABLED is False; skipping migrate_asterisk."
                )
            )
            return

        # Import the native migrate Command lazily so we get Django's
        # implementation, not the tenant-schemas override that the command
        # registry returns.
        from django.core.management.commands.migrate import Command as DjangoMigrate
        from django.db import connections

        migrate_cmd = DjangoMigrate(stdout=self.stdout, stderr=self.stderr)
        migrate_cmd.verbosity = int(opts.get("verbosity", 1))

        # Reconstruct the kwargs that Django's native migrate.handle expects.
        # Signature (as of Django 4.2): handle(app_label, migration_name, ...).
        handle_kwargs = {
            "app_label": "asterisk_state",
            "migration_name": opts.get("migration_name"),
            "database": "asterisk",
            "fake": opts.get("fake", False),
            "fake_initial": opts.get("fake_initial", False),
            "plan": opts.get("plan", False),
            "run_syncdb": opts.get("run_syncdb", False),
            "check_unapplied": False,
            "prune": False,
            "verbosity": migrate_cmd.verbosity,
            "interactive": False,
            "traceback": True,
            "no_color": True,
            "force_color": False,
            "skip_checks": True,
            "pythonpath": None,
            "settings": None,
        }

        # Make sure the alias is resolvable — fail loud if misconfigured.
        connections["asterisk"].ensure_connection()

        migrate_cmd.handle(**handle_kwargs)
