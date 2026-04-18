# Asterisk Realtime (ARA) cutover — pbx2.echodesk.cloud

This is the actual path that worked, captured from the live 2026-04-19 cutover.
Nothing here is theoretical; each step reflects a real-world gotcha we hit.

## End-state architecture

- **Shared Postgres DB**: the existing DigitalOcean managed cluster `dbaas-db-
  1965533`, database `defaultdb`, **schema `public`**. (Asterisk 18's
  `res_config_pgsql` hardcodes `public` in its `information_schema` lookup;
  search_path tricks don't work, so realtime tables live in `public`
  alongside app data.)
- **Role**: dedicated `asterisk_ro` role (LOGIN, SELECT/INSERT/UPDATE/DELETE
  on the 7 realtime tables, no access to anything else). Password stored in
  `/etc/asterisk/res_pgsql.conf` mode 640 asterisk:asterisk on pbx2, **not
  committed to git**.
- **7 tables**: `ps_endpoints`, `ps_auths`, `ps_aors`, `ps_identifies`,
  `ps_registrations`, `queues`, `queue_members`. Created by Django
  migration `asterisk_state.0001_initial` via `manage.py migrate_asterisk`.
  `ps_contacts` is auto-created by Asterisk on first PJSIP registration.
- **Row IDs are tenant-prefixed**: `amanati_100`, `amanati_support`,
  `amanati_trunk_geo_provider_magti_sip`. `AsteriskStateSync.prefix()` is
  the single point where this naming happens.
- **Sorcery config**: realtime wizard listed FIRST, then file fallback.
  Existing `[100]` / `[101]` / `[geo-provider]` blocks in `pjsip.conf`
  keep working during handover — softphones registered to `100` stay
  registered; the realtime endpoint `amanati_100` is a new name they can
  move to later.

## Gotchas we hit — in order

1. **DO Postgres firewall blocks the PBX by default.** pbx2's public IP
   (`185.229.109.65`) must be added to the managed DB's trusted sources.
   Symptom: `res_config_pgsql` hangs at startup → systemd kills Asterisk
   after `TimeoutStartSec=90s`. Fix: DO dashboard → Databases → Settings →
   Trusted Sources → add the PBX IP.
2. **`res_config_pgsql` must be preloaded.** Otherwise it autoloads AFTER
   `res_pjsip`, and PJSIP's sorcery wizard registration fails with
   "Wizard 'realtime' failed to open mapping for object type 'endpoint'".
3. **`extconfig.conf` only reads the first `[settings]` stanza.** Appending
   another `[settings]` at the bottom of the file does nothing — Asterisk
   silently ignores it. Mappings must go inside the existing `[settings]`
   block at the top.
4. **`extconfig.conf` database-context field must match a section in
   `res_pgsql.conf`.** `res_config_pgsql` only supports the `[general]`
   section, so extconfig entries use `pgsql,general,<table>`, not
   `pgsql,asterisk,<table>`.
5. **`[res_pjsip]` sorcery section can only list valid res_pjsip object
   types.** `registration` belongs under `[res_pjsip_outbound_registration]`
   and `phoneprov` under its own module. Putting them in `[res_pjsip]`
   causes a segfault / "uninitialized type" error at startup.
6. **`search_path` doesn't work** for Asterisk's pgsql driver because the
   driver's information_schema queries filter by `public`. The simplest fix
   is to keep realtime tables in the `public` schema. We tried a dedicated
   `asterisk_state` schema and it won't work.
7. **DO Postgres requires SSL.** `res_config_pgsql` doesn't expose an
   sslmode setting — set `PGSSLMODE=require` via a systemd drop-in so
   libpq reads it from the asterisk process env.
8. **fail2ban's `sshd` jail will ban your control-plane IP** if you poll
   `systemctl is-active` in a tight loop during a restart. Use `until`
   with a ≥3s interval.

## Files on pbx2 (as deployed)

### `/etc/asterisk/modules.conf`
```
[modules]
preload => res_config_pgsql.so
autoload=yes
noload => chan_sip.so
```

### `/etc/asterisk/res_pgsql.conf`
```ini
[general]
dbhost=dbaas-db-1965533-do-user-24154254-0.d.db.ondigitalocean.com
dbport=25060
dbname=defaultdb
dbuser=asterisk_ro
dbpass=<redacted — see /tmp/asterisk_ro_password.txt on the admin workstation>
dbappname=asterisk-pbx2
requirements=warn
```

### `/etc/asterisk/extconfig.conf` (within the existing `[settings]` stanza)
```ini
[settings]
; ...existing commented examples...
ps_endpoints => pgsql,general,ps_endpoints
ps_auths => pgsql,general,ps_auths
ps_aors => pgsql,general,ps_aors
ps_identifies => pgsql,general,ps_identifies
ps_registrations => pgsql,general,ps_registrations
ps_contacts => pgsql,general,ps_contacts
queues => pgsql,general,queues
queue_members => pgsql,general,queue_members
```

### `/etc/asterisk/sorcery.conf` (appended at end of file)
```ini
[res_pjsip]
endpoint=realtime,ps_endpoints
endpoint=config,pjsip.conf,criteria=type=endpoint
auth=realtime,ps_auths
auth=config,pjsip.conf,criteria=type=auth
aor=realtime,ps_aors
aor=config,pjsip.conf,criteria=type=aor
system=config,pjsip.conf,criteria=type=system
global=config,pjsip.conf,criteria=type=global
transport=config,pjsip.conf,criteria=type=transport
domain_alias=config,pjsip.conf,criteria=type=domain_alias

[res_pjsip_endpoint_identifier_ip]
identify=realtime,ps_identifies
identify=config,pjsip.conf,criteria=type=identify

[res_pjsip_outbound_registration]
registration=config,pjsip.conf,criteria=type=registration
```

### `/etc/systemd/system/asterisk.service.d/pgsql-env.conf`
```ini
[Service]
Environment="PGSSLMODE=require"
```

### `/etc/systemd/system/asterisk.service.d/timeout.conf` (safety net)
```ini
[Service]
TimeoutStartSec=300
```

## Verification

```bash
asterisk -rx 'realtime show pgsql status'
# → Connected to defaultdb@... with username asterisk_ro for N seconds

asterisk -rx 'pjsip show endpoints' | grep Endpoint:
# Expect file-based (100, 101, geo-provider-endpoint) AND
# realtime (amanati_100, amanati_101, amanati_trunk_…).

asterisk -rx 'queue show amanati_support'
# Expect strategy=rrmemory with PJSIP/amanati_100 and PJSIP/amanati_101
# members tagged (realtime).
```

## Rollback

```bash
systemctl stop asterisk
for f in sorcery extconfig res_pgsql; do
  BAK=$(ls -t /etc/asterisk/$f.conf.bak.* | head -1)
  cp "$BAK" /etc/asterisk/$f.conf
done
cp /etc/asterisk/modules.conf.bak.* /etc/asterisk/modules.conf
rm -f /etc/systemd/system/asterisk.service.d/pgsql-env.conf
rm -f /etc/systemd/system/asterisk.service.d/timeout.conf
systemctl daemon-reload
systemctl reset-failed asterisk
systemctl start asterisk
```

This reverts Asterisk to file-only config. Realtime tables in the DB stay
populated but untouched. `ASTERISK_SYNC_ENABLED=True` on Django is still
fine — Django keeps writing to the tables, Asterisk just stops reading.

## Next steps (not done yet)

- After a week of stable operation: remove the hand-written `[100]` /
  `[101]` / `[geo-provider]` blocks from `/etc/asterisk/pjsip.conf`.
  Reconfigure softphones to register as `amanati_100` / `amanati_101`.
- Rotate the `asterisk_ro` password and move it from
  `/etc/asterisk/res_pgsql.conf` to a systemd secret.
- Secure the recordings endpoint at `pbx2.echodesk.cloud:8443`.
