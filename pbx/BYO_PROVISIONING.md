# BYO Asterisk — provisioning runbook (support staff)

What happens when a tenant registers their own Asterisk server via the
EchoDesk UI.

## Prerequisites

- The tenant has a running Asterisk 18+ server they control, reachable on
  the public internet.
- Their server's public IP is in the DO Postgres trusted sources list
  (the tenant tells us their IP; we add it in the DO dashboard).

## Tenant-facing flow

1. Tenant admin opens `/settings/pbx/server/` → clicks **Connect your PBX**.
2. Fills in **name**, **FQDN**, **public IP**. Submits.
3. Backend (`PbxServerViewSet.perform_create`):
   - Creates a `PbxServer` row.
   - Calls `pbx_provisioning.provision_and_bootstrap(pbx)` which:
     - Creates Postgres DB `asterisk_<schema>` with owner `asterisk_rw_<schema>`.
     - Creates the RW role with a fresh random password (stored encrypted
       on the PbxServer row).
     - Grants USAGE + CREATE on `public` schema + default privileges for
       future tables.
     - Runs `python manage.py migrate_asterisk --database asterisk_<schema>`
       which applies the 7 realtime tables.
4. UI displays the one-line install command with a time-limited token.
5. Tenant runs:
   ```bash
   curl -sSL https://api.echodesk.ge/api/pbx/install/<token>/ | sudo bash
   ```
6. The install script:
   - Writes `/etc/asterisk/res_pgsql.conf` with their DB creds.
   - Injects sorcery + extconfig realtime mappings (matching
     `CUTOVER_RUNBOOK.md`'s proven config).
   - Adds `preload => res_config_pgsql.so` to modules.conf.
   - Sets `PGSSLMODE=require` + 300s start timeout via systemd drop-in.
   - Installs AMI user at `/etc/asterisk/manager.d/echodesk.conf`.
   - `systemctl restart asterisk`.
   - POSTs to `/api/pbx/install/<token>/ping` with the Asterisk version
     → backend flips `PbxServer.status=active`.

## Verifying a successful install

Run on the tenant's Asterisk server:

```bash
asterisk -rx 'realtime show pgsql status'
# → Connected to asterisk_<schema>@... with username asterisk_rw_<schema>

asterisk -rx 'pjsip show endpoints'
# → lists all endpoints, realtime ones tagged in the output

asterisk -rx 'queue show <queue_slug>'
# → members tagged (realtime)
```

In EchoDesk UI: `/settings/pbx/server/` shows **Active** status badge +
last-seen timestamp.

## Troubleshooting

- **`realtime show pgsql status` → Not connected** — check firewall (the
  tenant's public IP must be whitelisted on the DO Postgres cluster).
- **Install script hangs** — usually means Asterisk's startup hit the
  300s timeout waiting for pgsql. Check `journalctl -u asterisk` for
  `res_pjsip declined to load` or similar.
- **Token expired** — click **Regenerate install token** in the UI; TTL
  is 24h.
- **Status stuck on `provisioning`** — the install script never POSTed to
  `/ping`. Check network egress from the tenant's server to
  `api.echodesk.ge`. Manually flip the row via Django admin if needed.

## Rollback

1. Tenant edits `/etc/asterisk/res_pgsql.conf` + `sorcery.conf` +
   `extconfig.conf` — restore from the timestamped `.bak.*` files the
   install script created.
2. `systemctl restart asterisk`.
3. In EchoDesk UI, delete the `PbxServer` row — triggers backend cleanup
   (future enhancement: drop the Postgres DB + role too; for MVP this is
   manual).
