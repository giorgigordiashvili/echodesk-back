"""Apply Django migrations to a per-tenant Asterisk realtime DB alias.

Why this exists: ``django-tenant-schemas`` replaces Django's native ``migrate``
command with a thin wrapper that only understands ``--shared`` / ``--tenant``
on the default DB and strips ``--database``. That makes it impossible to run
migrations against secondary aliases through the normal path.

**Phase 2 (BYO Asterisk)**: there is no single ``asterisk`` alias anymore.
Each tenant registers a :class:`crm.models.PbxServer` whose credentials
define an ``asterisk_{schema}`` alias. This command can target:

- ``--database asterisk_acme`` — explicit alias (used during provisioning)
- ``--all`` — iterate every active PbxServer and migrate each one
- (legacy) no flag — log a notice and exit cleanly; there is no default
  target in Phase 2.

Usage::

    # Provisioning: migrate a freshly created tenant DB
    python manage.py migrate_asterisk --database asterisk_acme

    # Deploy-time: run pending migrations on every registered BYO server
    python manage.py migrate_asterisk --all

    python manage.py migrate_asterisk --all --plan     # show what would run
    python manage.py migrate_asterisk --all --fake     # record without executing
"""
from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Apply asterisk_state migrations to a per-tenant asterisk DB alias "
        "(bypasses tenant-schemas). Use --database <alias> or --all."
    )

    def add_arguments(self, parser):
        parser.add_argument("--plan", action="store_true")
        parser.add_argument("--fake", action="store_true")
        parser.add_argument("--fake-initial", action="store_true")
        parser.add_argument("--run-syncdb", action="store_true")
        parser.add_argument(
            "--database",
            dest="database",
            default=None,
            help="Alias of the asterisk DB to migrate (e.g. asterisk_acme).",
        )
        parser.add_argument(
            "--all",
            dest="all_servers",
            action="store_true",
            help="Migrate every registered active PbxServer's DB.",
        )
        parser.add_argument(
            "migration_name",
            nargs="?",
            help="Specific migration to apply (default: all pending).",
        )

    def handle(self, *args, **opts):
        if not getattr(settings, "ASTERISK_SYNC_ENABLED", True):
            self.stdout.write(
                self.style.WARNING(
                    "ASTERISK_SYNC_ENABLED is False; skipping migrate_asterisk."
                )
            )
            return

        database = opts.get("database")
        all_servers = opts.get("all_servers", False)

        if all_servers and database:
            raise CommandError("Pass either --all or --database, not both.")

        if all_servers:
            targets = self._collect_all_targets()
            if not targets:
                self.stdout.write(
                    self.style.WARNING(
                        "No active PbxServers found; nothing to migrate."
                    )
                )
                return
            for alias in targets:
                self._migrate_one(alias, opts)
            return

        if not database:
            self.stdout.write(
                self.style.NOTICE(
                    "No target specified. Pass --database <alias> or --all. "
                    "Phase 2 has no global default."
                )
            )
            return

        self._migrate_one(database, opts)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _collect_all_targets(self) -> list[str]:
        """Walk every tenant schema, register aliases for active PbxServers."""
        from crm.asterisk_db import register_pbx_alias
        from tenant_schemas.utils import schema_context
        from tenants.models import Tenant

        aliases: list[str] = []
        for tenant in Tenant.objects.exclude(schema_name='public'):
            try:
                with schema_context(tenant.schema_name):
                    from crm.models import PbxServer
                    pbx = PbxServer.objects.filter(
                        status=PbxServer.STATUS_ACTIVE
                    ).first()
                    if pbx is None:
                        continue
                    alias = register_pbx_alias(pbx, schema_name=tenant.schema_name)
                    aliases.append(alias)
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(
                    f"Failed to resolve PbxServer for tenant={tenant.schema_name}: {exc}"
                )
        return aliases

    def _migrate_one(self, alias: str, opts: dict) -> None:
        from django.core.management.commands.migrate import Command as DjangoMigrate
        from django.db import connections

        if alias not in connections.databases:
            raise CommandError(
                f"DB alias '{alias}' is not registered. Register it by calling "
                f"crm.asterisk_db.register_pbx_alias(pbx_server) first, or pass "
                f"--all to auto-register from PbxServer rows."
            )

        migrate_cmd = DjangoMigrate(stdout=self.stdout, stderr=self.stderr)
        migrate_cmd.verbosity = int(opts.get("verbosity", 1))

        handle_kwargs = {
            "app_label": "asterisk_state",
            "migration_name": opts.get("migration_name"),
            "database": alias,
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

        self.stdout.write(self.style.MIGRATE_HEADING(f"Migrating asterisk_state on {alias}"))
        connections[alias].ensure_connection()
        migrate_cmd.handle(**handle_kwargs)
