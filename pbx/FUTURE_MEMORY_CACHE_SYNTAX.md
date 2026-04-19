# Future: sorcery memory cache syntax for Asterisk realtime

## Why we want it

pbx2 lives in Tbilisi, our DO managed Postgres lives in Frankfurt. RTT
is **~60 ms** (measured 2026-04-18 from pbx2 → DO cluster).

Every inbound call triggers 2–3 realtime lookups at setup:
- `identify` → which endpoint does the incoming SIP source map to?
- `endpoint` → its config
- `auth` (sometimes) → credentials for challenge/response

At 60 ms/round-trip that's **120–180 ms of call-setup latency** from
the DB alone. Typical SIP setup is 100–500 ms end-to-end, so this is a
20–50 % overhead — not invisible to callers; they hear a longer
silence before the ring.

Asterisk's `res_sorcery_memory_cache` wizard solves this cleanly: first
lookup hits the DB, subsequent lookups read from in-process RAM for up
to the cache TTL. For a tenant with <100 endpoints the entire
realtime state fits in memory, call setup drops back to WAN-only
latency.

## What we tried (and why it failed)

Documented syntax per the Asterisk wiki:

```
[res_pjsip]
endpoint=memory_cache/realtime,ps_endpoints
auth=memory_cache/realtime,ps_auths
aor=memory_cache/realtime,ps_aors
```

Applied to pbx2 + restarted. `res_pjsip` declined to load with:

```
ERROR sorcery.c: Wizard 'memory_cache/realtime' could not be applied to
object type 'endpoint' as it was not found
```

`res_sorcery_memory_cache.so` **is** loaded (module show confirms). The
wizard name `memory_cache` alone resolves. The compound name
`memory_cache/realtime` does not — something about how the current
Ubuntu 22.04 Asterisk package (`1:18.10.0~dfsg+~cs6.10.40431411-2`)
parses the forward slash doesn't match the documented behaviour.

Rolled back to plain realtime; pbx2 is back to its pre-attempt state.

## Next things to try

1. **Different syntax variants** — a few exist across Asterisk versions:
   - `endpoint=memory_cache,realtime,ps_endpoints` (comma instead of slash)
   - Separate cache-config sections referenced by name
   - Multiple wizard stacking: `endpoint=memory_cache` then
     `endpoint=realtime,ps_endpoints` on the next line
2. **Upgrade Asterisk** — 18.20+ or 20.x may have fixed this. Our build
   is from Debian packages, not upstream; swapping to the official
   Asterisk repo + rebuild might behave differently.
3. **Patch Asterisk source** — the `sorcery.c` wizard lookup that
   rejects the slash form could be hot-patched, but that's a big
   commitment for a 60 ms win.
4. **Move the DB closer** — provision a DO Postgres cluster in a
   region nearer Tbilisi. DO regions closest to Georgia are Frankfurt
   (`fra1`) and Bangalore (`blr1`); neither is dramatically better
   than what we have. Other providers (Hetzner FSN1 — Falkenstein) are
   similar distance.

## Assessment

Worth ~1 day of investigation when we have 10+ tenants or when a
single customer's PBX is on a particularly bad network path. For now:

- **Amanati's 60–180 ms added latency is annoying but acceptable** —
  callers don't hang up over a quarter-second extra ring delay.
- **Future tenants whose PBX is colocated with Frankfurt** pay < 5 ms
  per round trip, making the cache unnecessary.
- The install script currently ships plain realtime (matches what's
  proven working on pbx2).

Re-open this investigation when:
- A tenant in Asia/Americas hits 150 ms+ RTT to the DO Postgres, OR
- We get a report of noticeably slow call setup, OR
- Someone finds the exact working syntax for 18.10 and posts it.
