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

