# EchoDesk Backend — Claude Development Notes

Guidance for Claude (and humans) working on `echodesk-back`. Frontend-specific
guidance lives in `echodesk-frontend/CLAUDE.md`.

## Project shape at a glance

- **Framework**: Django 4.2 multi-tenant via `django-tenant-schemas`. Each tenant
  gets its own Postgres schema; the `public` schema hosts shared/registry data.
- **Project package**: `amanati_crm` (legacy name). Settings, Celery app, ASGI
  live here.
- **Managed Postgres**: single DigitalOcean cluster, database `defaultdb`.
  Hosts both tenant schemas and the shared `asterisk_state` realtime schema.
- **Async**: Celery workers + beat, Redis on DB 2.
- **Real-time**: Django Channels via Redis DB 0, served by Daphne.
- **Multi-database**: two aliases in `DATABASES` — `default` (app data) and
  `asterisk` (Asterisk realtime). Routed by `amanati_crm.db_routers.
  AsteriskStateRouter`.

## PBX Management Panel — what exists

### Product models (tenant-schema, `crm/models.py`)

| Model | Purpose |
|---|---|
| `SipConfiguration` | Legacy per-tenant SIP trunk + WebRTC config. Kept for back-compat. |
| `UserPhoneAssignment` | User ↔ extension mapping. Source of truth for who owns which PJSIP endpoint. |
| `Trunk` | New per-tenant provider SIP trunk (Magti, Silknet, …). Owns DIDs. |
| `Queue` | Call queue backed by a `users.TenantGroup`. Members derive from the group + `UserPhoneAssignment`. |
| `QueueMember` | Derived rows, materialised by the sync layer. Read-only in the UI. |
| `InboundRoute` | DID → queue / extension / voicemail / custom IVR context / hangup. |
| `CallLog`, `CallEvent`, `CallRecording`, `CallRating`, `PbxSettings` | Pre-existing call operation records. |

### Asterisk realtime shadow models (`asterisk_state/models.py`)

Shadow `managed=True` tables mirroring Asterisk 18's realtime spec. Live in the
shared `asterisk_state` Postgres schema. Asterisk queries these on every call.

- `PsEndpoint`, `PsAuth`, `PsAor`, `PsIdentify`, `PsRegistration`
- `PsContact` (managed=False — Asterisk writes contact registrations here)
- `AsteriskQueue` (table `queues`), `AsteriskQueueMember` (table `queue_members`)

Rows use tenant-prefixed IDs to share a flat namespace: `amanati_100`,
`acme_support`, etc. The `AsteriskStateSync.prefix()` helper is the single
chokepoint for naming.

### Sync layer (`crm/asterisk_sync.py` + `crm/signals.py`)

Signals on product models write to the realtime shadow tables:

- `UserPhoneAssignment.save/delete` → upsert `PsEndpoint/PsAuth/PsAor/PsIdentify`
- `Trunk.save/delete` → trunk endpoint + auth + AOR + `PsRegistration`
- `Queue.save/delete` → `AsteriskQueue` row
- `User.tenant_groups` M2M change → recompute `queue_members` for affected queues
- `InboundRoute.save/delete` → no Asterisk write (dialplan runs via AGI that
  calls `/api/pbx/call-routing/` which resolves the route on demand)

Feature flag: `settings.ASTERISK_SYNC_ENABLED` is `True` iff `ASTERISK_DB_NAME`
is set (defaults to the main DB). When off, signals are no-ops.

Management commands:

```bash
# Run all pending Asterisk realtime migrations (tenant-schemas' migrate
# doesn't accept --database, so this wraps native migrate).
python manage.py migrate_asterisk [--plan] [--fake]

# Resync a single tenant's PBX state (or --all) into the realtime tables.
python manage.py sync_tenant_asterisk <schema_name>
python manage.py sync_tenant_asterisk --all

# Seed the amanati tenant with the PBX config currently live on pbx2.
python manage.py seed_amanati_pbx [--dry-run]
```

### API surface

- `GET /api/pbx/call-routing/?did=<e164>` — called by the Asterisk AGI.
  Resolves InboundRoute (by DID, then by owning Trunk's `phone_numbers`),
  returns working-hours state, sound URLs, destination extensions, queue
  name, tenant schema, inbound_route detail.
- `/api/trunks/`, `/api/queues/`, `/api/queue-members/`, `/api/inbound-routes/`
  — CRUD viewsets in `crm/views_pbx.py`, gated by the `ip_calling`
  subscription feature.
- `/api/call-stats/users/`, `.../users/<id>/timeline/`, `.../queues/`,
  `.../overview/` — DB-side aggregation endpoints in `crm/views_stats.py`.

### Feature key

All PBX-management endpoints + sidebar nav gate on **`ip_calling`** (not
`sip_calling`). The frontend, `CallContext`, and this app's own viewsets must
all reference the same key.

## Asterisk server (pbx2.echodesk.cloud)

- **Host**: 185.229.109.65 (DigitalOcean FRA1), Ubuntu 22.04, Asterisk 18.10.
- **SIP trunk**: Magti, user `1048444e3`, DID `+995322421219`, signalling
  89.150.1.11:5060.
- **TLS**: Let's Encrypt for `pbx2.echodesk.cloud` → WSS 8089 + nginx 8443
  (recording proxy).
- **AMI**: port 5038, user `echodesk`, ACL'd to the DO backend's egress IPs.

### Config files under source control (`pbx/`)

- `echodesk-routing.py` — AGI script. Queries `/api/pbx/call-routing/` and
  exports channel variables (`IS_WORKING`, `ROUTE_ACTION`, `QUEUE_NAME`,
  `QUEUE_SLUG`, `TENANT_SCHEMA`, `DEST_EXTENSIONS`, sound URLs, …). Deployed
  to `/var/lib/asterisk/agi-bin/`.
- `extensions-incoming.conf` — dialplan template. Uses `${QUEUE_TO_DIAL}`
  (derived from `QUEUE_NAME` with fallback to `support`) so the same context
  works before and after the realtime cutover.
- `DEPLOY_PBX2_SCRIPTS.md` — runbook for applying the AGI + dialplan on pbx2.

### Asterisk realtime (ARA) cutover — **LIVE**

Cut over on 2026-04-19. `pjsip show endpoints` lists both file-based
(`100`, `101`, `geo-provider-endpoint`) and realtime (`amanati_100`,
`amanati_101`, `amanati_trunk_…`) side-by-side. `queue show
amanati_support` reports its members as `(realtime)`.

- Realtime tables live in the **`public` schema** of `defaultdb`
  (Asterisk 18's pgsql driver hardcodes `public` in information_schema
  queries — a dedicated schema doesn't work). Row IDs are tenant-prefixed.
- Django's `asterisk` DB alias reuses the main DB creds (no separate env
  vars required on DO). `ASTERISK_SYNC_ENABLED` auto-flips to True.
- Asterisk connects as `asterisk_ro` with SELECT/INSERT/UPDATE/DELETE on
  just the 7 realtime tables (plus the auto-created `ps_contacts`).
- Full runbook with all gotchas at `pbx/CUTOVER_RUNBOOK.md`.

The hand-written `[100]`/`[101]`/`[geo-provider]` blocks in `pjsip.conf`
stay in place during the bedding-in period so existing softphones keep
working. After ~1 week stable, we retire those blocks and reconfigure
softphones to register as `amanati_100` / `amanati_101`.

## Deployment workflow

- **Backend** auto-deploys on push to `main` via DigitalOcean App Platform.
- `build_production.sh` runs:
  1. `python manage.py check --deploy`
  2. `python manage.py collectstatic --noinput`
  3. `python manage.py migrate_schemas --shared`
  4. `python manage.py migrate_asterisk` *(new — applies realtime schema
     changes through the native migrate command, bypassing the
     tenant-schemas wrapper)*
- Tenant-schema migrations are run **manually** before pushing via
  `python manage.py migrate_schemas --tenant`. The production DB is the only
  DB; there's no separate staging, so migrations should be reviewed carefully.

## Conventions / gotchas

- **Tenant isolation**: always wrap cross-schema work in
  `from tenant_schemas.utils import schema_context`:
  ```python
  with schema_context('amanati'):
      Queue.objects.create(...)
  ```
- **User → group relation**: `TenantGroup.members` (M2M `related_name`) is
  the reverse of `User.tenant_groups`. `user_set` does **not** exist.
- **Asterisk realtime uniqueness**: PJSIP reads from one flat namespace, so
  table rows are globally unique. Always go through
  `AsteriskStateSync.prefix(schema, name)` when naming realtime rows.
- **No per-tenant PBX server**: single `pbx.echodesk.cloud` (legacy, soon
  retired) + `pbx2.echodesk.cloud` (active). If we ever shard, add a
  `PbxServer` model and route per-tenant.
- **Recordings**: currently world-readable via `https://pbx2.echodesk.cloud:
  8443/recordings/<file>.wav` with `Access-Control-Allow-Origin: *`. Signing
  / auth proxy is a known security gap.

## Files to reference

- Plan doc: `~/.claude/plans/i-want-you-to-wondrous-trinket.md`
- Deployment runbook: `pbx/DEPLOY_PBX2_SCRIPTS.md`
- Frontend development notes: `../echodesk-frontend/CLAUDE.md`
