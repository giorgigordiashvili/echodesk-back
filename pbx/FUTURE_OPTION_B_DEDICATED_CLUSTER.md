# Future: move tenant Asterisk DBs to a dedicated Postgres cluster

> **Status**: not needed now. Today all `asterisk_<tenant>` databases live
> alongside `defaultdb` on the single DO cluster (Option A). This doc
> captures when + how we flip to a dedicated realtime cluster (Option B)
> so future-us doesn't have to re-derive the plan.

## Why this is worth doing *eventually*

| Risk under Option A | How Option B fixes it |
|---|---|
| A Postgres CVE in a subsystem both DBs share hits the app + every tenant's PBX data in one blast | Realtime cluster can be patched on its own cadence; app cluster stays independent |
| DO Trusted Sources list mixes **tenant PBX public IPs** with **our app infra IPs**. Auditing "who can reach our app DB" requires filtering out the PBX noise | Each cluster has its own allow-list. App cluster only knows our own IPs; realtime cluster only knows tenant PBX IPs |
| One backup / restore operation snapshots everything together. Restoring a tenant's PBX state in isolation requires filtering | Realtime cluster backups contain only PBX data. Clean per-tenant restore |
| If the Asterisk workload ever starts contending for the app DB (high-frequency realtime lookups), we can't tune the two separately | Tune the realtime cluster for connection count + small read-heavy workload; app cluster stays tuned for its OLTP pattern |

## Trigger conditions

Migrate to a dedicated realtime cluster **when any of these hit**:

- **≥ 10 active `PbxServer` rows** across all tenants.
- A single tenant has **explicit compliance requirement** (e.g., ISO, HIPAA-ish scoping, contractual data-isolation clause) that mandates their PBX data not share infra with other tenants' app data.
- DO Trusted Sources list exceeds **~20 IPs** and becomes hard to audit.
- `pg_stat_activity` on the app cluster shows `asterisk_rw_*` connections consistently consuming a significant share of the connection pool.
- Asterisk realtime lookup latency p95 exceeds **50 ms** (currently sub-5 ms).

## End-state architecture

```
dbaas-db-1965533         ← app cluster, unchanged
  └── defaultdb            EchoDesk app data only

dbaas-db-pbx-realtime    ← NEW dedicated realtime cluster
  ├── asterisk_amanati     (moved)
  ├── asterisk_acme
  └── …                    (every new BYO tenant lands here)
```

Both clusters stay on DO managed Postgres. Cost delta: **+~$15/month**
for the smallest realtime cluster size. Can be downsized further if
usage stays minimal.

## Migration recipe (30 minutes of work, zero downtime)

### 1. Provision the new cluster

Via DO dashboard OR `doctl`:

```bash
doctl databases create pbx-realtime \
  --engine pg --version 16 --region fra1 \
  --size db-s-1vcpu-1gb --num-nodes 1
```

Add the **current app infra IPs** to its Trusted Sources (for Django
writes) PLUS every currently-registered `PbxServer.public_ip` (for
Asterisk reads). The install script already sends us their IP; pull the
list:

```sql
-- Against the app cluster
SELECT public_ip FROM (
  -- One query per tenant schema — or use manage.py shell with an
  -- --all loop through PbxServer.objects
) ORDER BY public_ip;
```

### 2. Plumb a second Django DB alias

Add to `amanati_crm/settings.py` alongside the existing `default`:

```python
# When unset (Option A), per-tenant asterisk aliases inherit default's
# host. When set (Option B), they use this instead.
ASTERISK_CLUSTER_HOST = config('ASTERISK_CLUSTER_HOST', default=_default_db.get('HOST'))
ASTERISK_CLUSTER_PORT = config('ASTERISK_CLUSTER_PORT', default=_default_db.get('PORT'))
ASTERISK_CLUSTER_ADMIN_USER = config('ASTERISK_CLUSTER_ADMIN_USER', default=_default_db.get('USER'))
ASTERISK_CLUSTER_ADMIN_PASSWORD = config('ASTERISK_CLUSTER_ADMIN_PASSWORD', default=_default_db.get('PASSWORD'))
```

Update `crm/pbx_provisioning.py::_admin_dsn()` to read these instead
of hardcoding `DATABASES['default']`. Then new tenants are provisioned
straight onto the new cluster.

### 3. Migrate existing tenants' DBs

For each active `PbxServer`:

```bash
# 1. Dump from old cluster
pg_dump \
  "postgresql://doadmin:$OLD_PW@old-host:25060/asterisk_amanati?sslmode=require" \
  --no-owner --no-privileges \
  > /tmp/asterisk_amanati.sql

# 2. Create the database + role on the new cluster
psql "postgresql://doadmin:$NEW_PW@new-host:25060/defaultdb?sslmode=require" <<SQL
CREATE DATABASE asterisk_amanati;
CREATE ROLE asterisk_rw_amanati LOGIN PASSWORD '<rotate>';
GRANT CONNECT ON DATABASE asterisk_amanati TO asterisk_rw_amanati;
SQL

# 3. Restore
psql \
  "postgresql://doadmin:$NEW_PW@new-host:25060/asterisk_amanati?sslmode=require" \
  < /tmp/asterisk_amanati.sql

# 4. Re-apply grants inside the new DB
psql "postgresql://doadmin:$NEW_PW@new-host:25060/asterisk_amanati?sslmode=require" <<SQL
GRANT USAGE, CREATE ON SCHEMA public TO asterisk_rw_amanati;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO asterisk_rw_amanati;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO asterisk_rw_amanati;
SQL

# 5. Update the tenant's PbxServer to point at the new cluster
python manage.py shell -c "
from tenant_schemas.utils import schema_context
with schema_context('amanati'):
    from crm.models import PbxServer
    pbx = PbxServer.objects.first()
    pbx.realtime_db_host = '<new-host>'
    pbx.realtime_db_password = '<rotated password>'
    pbx.save()
"

# 6. Regenerate the install token and re-run the install script on
#    pbx2 (or hand-edit /etc/asterisk/res_pgsql.conf with the new
#    creds + systemctl restart asterisk)
```

### 4. Decommission the old DBs

After a week of stable operation on the new cluster:

```sql
-- Against OLD cluster
DROP DATABASE asterisk_amanati;
DROP ROLE asterisk_rw_amanati;
-- Repeat per tenant
```

## What's already Option-B-ready

- **`PbxServer` stores its own host/port/user/password/SSL mode per row**
  (`crm/models.py::PbxServer`). Migration is purely "update the fields"
  — no schema change, no code refactor.
- **Dynamic DB alias registration** (`crm/asterisk_db.py::register_pbx_alias`)
  reads the host off the model — zero Django-side change required.
- **Install script** (`crm/views_pbx_install.py`) embeds credentials at
  render time, so re-running it writes the new connection config.

## What's Option-A-specific to change

- `crm/pbx_provisioning.py::_admin_dsn()` currently inherits from
  `DATABASES['default']`. Add the `ASTERISK_CLUSTER_*` env-var fallback
  described above.
- Documentation / onboarding runbooks that reference "our single DO
  cluster" (this file + `BYO_PROVISIONING.md`) get a paragraph update.

## Cost check

- Smallest DO managed Postgres: db-s-1vcpu-1gb, ~$15/month.
- Typical realtime workload per tenant: <10 connections, <1 MB/s writes,
  tiny row counts (tens to low hundreds of rows per tenant).
- A single db-s-1vcpu-1gb instance comfortably handles 50+ tenants at
  current shape. Scale up only if `pg_stat_statements` shows contention.
