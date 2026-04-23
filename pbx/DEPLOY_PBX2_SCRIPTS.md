# Deploying PBX scripts to pbx2.echodesk.cloud

The AGI script and dialplan in this `pbx/` directory now consume the new
`queue_name` / `queue_slug` / `inbound_route` fields returned by
`/api/pbx/call-routing/` (populated from `InboundRoute` + `Queue` models).

This is a **one-time manual update** on `pbx2.echodesk.cloud` (185.229.109.65).
The ARA (Asterisk Realtime) cutover is still pending, so the queue name sent
by the API is the bare slug (`support`) — which matches what Asterisk has in
`queues.conf` today. After the ARA migration we'll flip
`ASTERISK_SYNC_ENABLED=True` and the API will return `amanati_support`; the
dialplan is already tolerant of either.

## 1. Push the updated AGI script

From your laptop:

```bash
scp echodesk-back/pbx/echodesk-routing.py \
    root@185.229.109.65:/var/lib/asterisk/agi-bin/echodesk-routing.py
ssh root@185.229.109.65 'chmod +x /var/lib/asterisk/agi-bin/echodesk-routing.py'
```

Verify on the server:

```bash
ssh root@185.229.109.65 \
  'head -n 3 /var/lib/asterisk/agi-bin/echodesk-routing.py && \
   grep -c QUEUE_NAME /var/lib/asterisk/agi-bin/echodesk-routing.py'
```

The grep should return `>= 2` lines.

## 2. Update the live dialplan on pbx2

The live dialplan on pbx2 uses `[from-provider]` + `[queue-with-announce]` (not
the `[incoming]` context in this repo's `extensions-incoming.conf`). Apply the
same change directly to `/etc/asterisk/extensions.conf`:

1. SSH in and back up: `cp /etc/asterisk/extensions.conf{,.bak.$(date +%F)}`.
2. Edit the `[from-provider]` context so the `Queue()` application uses
   `${QUEUE_NAME}` with a fallback:

    ```asterisk
    [from-provider]
    ; … existing answer + AGI steps …
    same => n,Set(QUEUE_TO_DIAL=${IF($["${QUEUE_NAME}" != ""]?${QUEUE_NAME}:support)})
    same => n,Goto(queue-with-announce,${EXTEN},1)

    [queue-with-announce]
    exten => _X.,1,NoOp(Entering queue ${QUEUE_TO_DIAL})
    same => n,Queue(${QUEUE_TO_DIAL},t,,,60)
    ; … rest unchanged …
    ```

3. Reload dialplan:

    ```bash
    asterisk -rx 'dialplan reload'
    ```

## 3. Smoke test

```bash
# Simulate the API call the AGI makes
curl -s -H "Authorization: Bearer ${PBX_SHARED_SECRET}" \
  'https://api.echodesk.ge/api/pbx/call-routing/?did=%2B995322421219' | jq .
```

Expected response includes:

```json
{
  "queue_name": "support",
  "queue_slug": "support",
  "tenant_schema": "amanati",
  "inbound_route": {
    "id": <n>,
    "did": "+995322421219",
    "destination_type": "queue",
    "queue_slug": "support",
    "queue_name": "support",
    "priority": 100
  },
  "extensions": ["100", "101", …]
}
```

Place a real inbound call to `+995 32 242 1219` and tail the log:

```bash
ssh root@185.229.109.65 'tail -f /var/log/asterisk/echodesk-routing.log'
```

The log should show `queue=support, tenant=amanati`.

## 4. After-ARA-cutover follow-up

Once `ASTERISK_SYNC_ENABLED=True` + the realtime migration is applied, the
API starts returning `queue_name: amanati_support`. The dialplan change in
step 2 already handles it — no script changes needed at that point.

## 5. Widget voice-call context

PR 7 of the embeddable chat widget adds a `[widget-call-<tenant>]` dialplan
context used by ephemeral guest PJSIP endpoints created for visitors who
click the "Call" button. Endpoints are provisioned by
`/api/widget/public/call/credentials/` via
`AsteriskStateSync.sync_widget_guest_endpoint`, which sets the endpoint's
pjsip `context` to `widget-call-<tenant_schema>`. That context must exist
on pbx2 before widget calls will land.

The canonical template lives in this repo at
`pbx/extensions-incoming.conf` (look for `[widget-call-amanati]`). Copy
that block into `/etc/asterisk/extensions.conf` on pbx2 and reload:

```bash
ssh root@185.229.109.65
# Append the [widget-call-amanati] block from pbx/extensions-incoming.conf
# (adjust the static filename if you've diverged); then:
asterisk -rx 'dialplan reload'
asterisk -rx 'dialplan show widget-call-amanati'
```

Smoke-test:

1. Toggle `voice_enabled = true` on a WidgetConnection.
2. Visit the widget host page; click the "Call" button (once PR 8 lands).
3. Inspect the Asterisk CLI: `pjsip show endpoint widget_<session_id>`
   should show a registered contact and the call should hit the
   tenant's `support` queue.

The ephemeral endpoint is cleaned up after 4h of session inactivity by
the hourly Celery task `social_integrations.reap_stale_widget_endpoints`
(also callable as `python manage.py reap_stale_widget_endpoints --dry-run`).

When a second tenant enables widget voice, add a `[widget-call-<schema>]`
block for them. A future PR will generate these programmatically.
