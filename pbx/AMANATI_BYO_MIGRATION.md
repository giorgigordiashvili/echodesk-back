# Amanati retrofit to BYO — done 2026-04-19

amanati's pbx2.echodesk.cloud is their own Asterisk (not shared EchoDesk
infra). This records how we cut them over from the shared
`defaultdb.public` realtime schema with tenant-prefixed IDs to their own
`asterisk_amanati` DB with clean unprefixed IDs.

## State before

- `defaultdb.public.ps_endpoints` held: `amanati_100`, `amanati_101`,
  `amanati_trunk_geo_provider_magti_sip`.
- `defaultdb.public.queues.name = 'amanati_support'`.
- `defaultdb.public.queue_members` referenced the prefixed names.
- Asterisk on pbx2 connected as role `asterisk_ro` (SELECT-only on public).

## Steps executed

1. `PbxServer` created in the amanati tenant schema via a shell one-liner
   (equivalent to what the UI does on **Connect your PBX**):
   ```python
   pbx = PbxServer(
       name='Amanati PBX', fqdn='pbx2.echodesk.cloud',
       public_ip='185.229.109.65', ami_username='echodesk',
       ami_password='EchoDesk_AMI_2024!', use_tenant_prefix=False,
   )
   pbx.save()
   provision_and_bootstrap(pbx)
   ```
   → Created `asterisk_amanati` DB and `asterisk_rw_amanati` role, ran
   `asterisk_state` migration.

2. Flipped `PbxServer.status=active` manually (the install script is the
   normal path, but amanati's Asterisk already has the realtime config
   files from Phase 1; no re-install needed).

3. `python manage.py sync_tenant_asterisk amanati` — wrote 3 endpoints +
   1 queue + 2 queue members with **unprefixed IDs** (`100`, `101`,
   `support`) into `asterisk_amanati`.

4. Generated new `/etc/asterisk/res_pgsql.conf` with `asterisk_rw_amanati`
   creds pointed at `asterisk_amanati`; SCP'd to pbx2; replaced the old
   one. `systemctl restart asterisk`.

5. Verified on pbx2:
   ```
   asterisk -rx 'realtime show pgsql status'
   # Connected to asterisk_amanati@... with username asterisk_rw_amanati
   asterisk -rx 'pjsip show endpoint 100'
   # ← unprefixed, realtime-loaded
   asterisk -rx 'queue show support'
   # ← members tagged (realtime)
   ```

## State after

- Asterisk on pbx2 reads from `asterisk_amanati` DB (isolated from all
  other tenants + from EchoDesk app data).
- Endpoint IDs are `100`, `101`, `trunk_geo_provider_magti_sip` — no
  tenant prefix clutter.
- The legacy `amanati_*` rows still live in `defaultdb.public` — harmless
  but should be cleaned up (see below).
- `asterisk_ro` role still exists with grants on `defaultdb.public` — can
  be revoked.

## Follow-up cleanup (still TODO)

```sql
-- 1. Delete leftover amanati_* rows from the shared public schema.
DELETE FROM public.ps_endpoints WHERE id LIKE 'amanati_%';
DELETE FROM public.ps_auths     WHERE id LIKE 'amanati_%';
DELETE FROM public.ps_aors      WHERE id LIKE 'amanati_%';
DELETE FROM public.ps_identifies WHERE id LIKE 'amanati_%';
DELETE FROM public.queue_members WHERE queue_name LIKE 'amanati_%';
DELETE FROM public.queues        WHERE name LIKE 'amanati_%';

-- 2. Revoke grants on the old role (only when no other server uses it).
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM asterisk_ro;
DROP OWNED BY asterisk_ro;
DROP ROLE asterisk_ro;
```

Do these **after** at least a week of stable calls on the new config, so
rollback (restoring the old res_pgsql.conf) stays trivial.
