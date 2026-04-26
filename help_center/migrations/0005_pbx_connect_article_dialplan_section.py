"""Update the 'Connect your Asterisk' article with the dialplan section
plus troubleshooting entries for the issues that surfaced on amanati's
production cutover (2026-04-26):

1. **Per-tenant dialplan contexts** — `AsteriskStateSync` writes PJSIP
   realtime rows with `context = "tenant_<schema>"` (agent endpoints)
   and `from-provider-<schema>` (trunks). These context names MUST exist
   in `/etc/asterisk/extensions.conf` or every call gets rejected with
   "extension not found in context …". The install script doesn't seed
   the dialplan — tenants own their routing logic — so the article needs
   a step that explains the alias pattern.

2. **Codec mismatch (opus → ulaw)** — symptom: agent picks up the call
   from the browser softphone and it drops within a second. Root cause:
   trunk allow-list is `ulaw,alaw,g722` while WebRTC endpoint advertises
   Opus that Asterisk can't transcode without `codec_opus.so`. As of
   commit 2d3b03d the sync drops Opus from the WebRTC defaults; old
   tenants need to resync.

3. **Caller display shows the agent's own extension** — symptom: an
   inbound call labels the caller as "101" instead of the real phone
   number. Root cause: legacy sync set `from_user = <extension>` on the
   WebRTC endpoint which forces the From URI's user portion. Commit
   2fcb697 stops setting it; old tenants need to clear it from the
   realtime DB.
"""
from django.db import migrations


ARTICLE_SLUG = "connect-your-asterisk"


# Reuse the styling tokens defined in the v0.4 migration so the new
# blocks render identically. Duplicating them here keeps this migration
# self-contained against future code refactors.

STEP_CIRCLE_STYLE = (
    "width:40px;height:40px;border-radius:9999px;"
    "display:flex;align-items:center;justify-content:center;"
    "background:hsl(var(--primary));color:hsl(var(--primary-foreground));"
    "font-weight:700;font-size:1.125rem;line-height:1;"
    "box-shadow:0 4px 6px -1px rgba(0,0,0,.1);flex-shrink:0;"
)
STEP_ROW_STYLE = "display:flex;gap:1rem;margin:2rem 0;"
CARD_STYLE = (
    "border:1px solid hsl(var(--border));border-radius:0.75rem;"
    "padding:1rem 1.25rem;background:hsl(var(--card));"
)
REQ_ICON_STYLE = (
    "width:36px;height:36px;border-radius:0.5rem;display:flex;"
    "align-items:center;justify-content:center;flex-shrink:0;"
    "background:color-mix(in srgb, hsl(var(--primary)) 15%, transparent);"
    "color:hsl(var(--primary));font-weight:700;"
)
CODE_BLOCK_STYLE = (
    "background:hsl(240 10% 6%);color:hsl(0 0% 98%);"
    "border:1px solid hsl(240 5% 15%);border-radius:0.5rem;"
    "padding:1rem 1.25rem;font-size:0.8125rem;line-height:1.6;"
    "overflow-x:auto;margin:0.75rem 0;"
)
INLINE_CODE_STYLE = (
    "background:hsl(var(--muted));color:hsl(var(--primary));"
    "padding:0.125rem 0.375rem;border-radius:0.25rem;font-size:0.8125rem;"
)
ALERT_WARN_STYLE = (
    "border-left:4px solid hsl(38 92% 50%);"
    "background:color-mix(in srgb, hsl(38 92% 50%) 10%, transparent);"
    "color:hsl(var(--foreground));"
    "border-radius:0.5rem;padding:0.875rem 1rem;margin:1.25rem 0;"
    "font-size:0.875rem;line-height:1.6;"
)
ALERT_TIP_STYLE = (
    "border-left:4px solid hsl(142 71% 45%);"
    "background:color-mix(in srgb, hsl(142 71% 45%) 10%, transparent);"
    "color:hsl(var(--foreground));"
    "border-radius:0.5rem;padding:0.875rem 1rem;margin:1.25rem 0;"
    "font-size:0.875rem;line-height:1.6;"
)
NOTE_STYLE = (
    "border:1px solid hsl(var(--border));background:hsl(var(--muted)/0.4);"
    "border-radius:0.5rem;padding:0.75rem 1rem;margin:1rem 0;"
    "font-size:0.8125rem;line-height:1.55;color:hsl(var(--foreground));"
)
DETAILS_STYLE = (
    "border:1px solid hsl(var(--border));background:hsl(var(--card));"
    "border-radius:0.5rem;margin:0.75rem 0;overflow:hidden;"
)
SUMMARY_STYLE = (
    "cursor:pointer;user-select:none;padding:0.875rem 1.25rem;"
    "font-weight:600;font-size:0.9375rem;color:hsl(var(--foreground));"
)
HERO_STYLE = (
    "border-radius:1rem;padding:2rem;margin-bottom:2.5rem;"
    "border:1px solid hsl(var(--border));"
    "background:linear-gradient(135deg, "
    "color-mix(in srgb, hsl(var(--primary)) 12%, transparent), "
    "color-mix(in srgb, hsl(var(--primary)) 4%, transparent) 60%, "
    "transparent);"
)
PILL_BASE = (
    "display:inline-flex;align-items:center;border-radius:9999px;"
    "padding:0.25rem 0.75rem;font-size:0.75rem;font-weight:600;"
    "margin-right:0.5rem;margin-bottom:0.5rem;"
)


def step(number: int, title: str, body: str) -> str:
    return f"""
<div class="not-prose" style="{STEP_ROW_STYLE}">
  <div style="{STEP_CIRCLE_STYLE}">{number}</div>
  <div style="flex:1;padding-top:0.25rem;">
    <h3 style="font-size:1.25rem;font-weight:600;margin:0 0 0.5rem 0;color:hsl(var(--foreground));">{title}</h3>
    <div style="color:hsl(var(--muted-foreground));font-size:0.9375rem;line-height:1.65;">
      {body}
    </div>
  </div>
</div>
"""


def code(content: str) -> str:
    return f'<pre class="not-prose" style="{CODE_BLOCK_STYLE}"><code>{content}</code></pre>'


def ic(text: str) -> str:
    return f'<code style="{INLINE_CODE_STYLE}">{text}</code>'


def req_card(letter: str, title: str, body: str) -> str:
    return f"""
<div class="not-prose" style="{CARD_STYLE}display:flex;gap:0.75rem;align-items:flex-start;">
  <div style="{REQ_ICON_STYLE}">{letter}</div>
  <div>
    <p style="font-weight:600;margin:0 0 0.25rem 0;color:hsl(var(--foreground));">{title}</p>
    <p style="margin:0;color:hsl(var(--muted-foreground));font-size:0.875rem;line-height:1.55;">{body}</p>
  </div>
</div>
"""


# --- Pre-formatted code blocks --------------------------------------------
# Defined as module-level strings (not inside f-strings) so we can use
# escape sequences like \n / \' freely. Python 3.9 disallows backslashes
# inside f-string expression curlies, so we just reference these directly.

_CODEC_LOG_BLOCK = code(
    "No path to translate from PJSIP/&lt;ext&gt; to PJSIP/&lt;trunk&gt;\n"
    "Had to drop call because I couldn't make ... compatible"
)

_FROM_USER_VERIFY_BLOCK = code(
    "asterisk -rx 'pjsip show endpoint &lt;ext&gt;' | grep from_user\n"
    "# from_user                           : "
)


# --- English ---------------------------------------------------------------

TITLE = {
    "en": "Connect your Asterisk to EchoDesk",
    "ka": "დააკავშირეთ თქვენი Asterisk EchoDesk-თან",
    "ru": "Подключите Asterisk к EchoDesk",
}

SUMMARY = {
    "en": (
        "Bring your own Asterisk 18+ server and manage extensions, queues, "
        "trunks and inbound routing from EchoDesk. Changes take effect in "
        "seconds — no SSH, no file edits, no reloads."
    ),
    "ka": (
        "დააკავშირეთ საკუთარი Asterisk 18+ სერვერი და მართეთ ხაზები, რიგები, "
        "ტრანკები და შემოსული ზარები EchoDesk-დან."
    ),
    "ru": (
        "Подключите свой сервер Asterisk 18+ и управляйте расширениями, "
        "очередями, транками и входящей маршрутизацией из EchoDesk."
    ),
}


HERO_EN = f"""
<div class="not-prose" style="{HERO_STYLE}">
  <div style="margin-bottom:1rem;">
    <span style="{PILL_BASE}background:hsl(var(--primary));color:hsl(var(--primary-foreground));">Self-service</span>
    <span style="{PILL_BASE}background:color-mix(in srgb, hsl(142 71% 45%) 18%, transparent);color:hsl(142 71% 40%);">~10 min setup</span>
    <span style="{PILL_BASE}background:color-mix(in srgb, hsl(217 91% 60%) 18%, transparent);color:hsl(217 91% 60%);">Asterisk 18+</span>
  </div>
  <p style="font-size:1rem;color:hsl(var(--foreground));line-height:1.65;margin:0;">
    Bring your own Asterisk server and manage <strong>extensions</strong>,
    <strong>queues</strong>, <strong>trunks</strong> and <strong>inbound routing</strong>
    directly from the EchoDesk admin panel. Most config — endpoints, AORs,
    auths, identifies, queues, trunks — flows live from EchoDesk into your
    Asterisk's realtime database. The dialplan in {ic("/etc/asterisk/extensions.conf")}
    stays under your control: it's the only part you edit by hand, and you
    only have to do it once.
  </p>
</div>
"""

REQUIREMENTS_EN = f"""
<div class="not-prose" style="display:grid;gap:0.75rem;grid-template-columns:repeat(2, minmax(0, 1fr));margin:1.5rem 0;">
  {req_card("A", "Asterisk 18 or newer", "On a Linux server you control. We talk to Asterisk via its realtime driver, which is standard in Asterisk 18+.")}
  {req_card("B", "Public FQDN + TLS cert", "e.g. pbx.mycompany.com. Let's Encrypt is fine — browsers refuse self-signed certs for WebSocket softphones.")}
  {req_card("C", "Outbound 25060/tcp", "For Asterisk's realtime DB connection to our managed Postgres cluster.")}
  {req_card("D", "Inbound 8089/tcp (WSS)", "So softphones can register. Plus your SIP provider's signalling port.")}
  {req_card("E", "Root / sudo access", "The install script writes under /etc/asterisk/ and adds a systemd drop-in.")}
  {req_card("F", "No database needed locally", "We host your realtime DB on our managed Postgres. You only provide the Asterisk server.")}
</div>
"""


DIALPLAN_EXAMPLE_EN = code(
    "; ---------------------------------------------------------------------\n"
    "; PER-TENANT ALIAS CONTEXTS  ← REPLACE &lt;your-schema&gt; with your tenant slug\n"
    "; e.g. if your dashboard URL is acme.echodesk.ge, the schema is `acme`.\n"
    "; ---------------------------------------------------------------------\n"
    "[from-provider-&lt;your-schema&gt;]\n"
    "include =&gt; from-provider\n"
    "\n"
    "[tenant_&lt;your-schema&gt;]\n"
    "include =&gt; from-internal\n"
    "\n"
    "; ---------------------------------------------------------------------\n"
    "; INBOUND TRUNK HANDLER (your existing logic)\n"
    "; ---------------------------------------------------------------------\n"
    "[from-provider]\n"
    "exten =&gt; s,1,NoOp(Inbound from provider: ${CALLERID(num)})\n"
    " same =&gt; n,Answer()\n"
    " same =&gt; n,Queue(support,t,,,60)   ; route to your queue\n"
    " same =&gt; n,Hangup()\n"
    "\n"
    "exten =&gt; _X.,1,Goto(s,1)            ; catch-all inbound\n"
    "\n"
    "; ---------------------------------------------------------------------\n"
    "; OUTBOUND FROM EXTENSIONS  (E.164, GE-style numbers, internal dial)\n"
    "; ---------------------------------------------------------------------\n"
    "[from-internal]\n"
    "exten =&gt; _+X.,1,Set(CALLERID(num)=&lt;your-trunk-DID&gt;)\n"
    " same =&gt; n,Dial(PJSIP/${EXTEN}@&lt;your-trunk-endpoint&gt;,60,r)\n"
    " same =&gt; n,Hangup()\n"
    "\n"
    "exten =&gt; _1XX,1,Dial(PJSIP/${EXTEN},30,r)   ; internal extension-to-extension\n"
    " same =&gt; n,Hangup()\n"
)


CONTENT_EN = (
    HERO_EN
    + "<h2>Before you start</h2>"
    + REQUIREMENTS_EN
    + f"""
<div class="not-prose" style="{ALERT_TIP_STYLE}">
  <p style="margin:0;">
    <strong style="color:hsl(142 71% 40%);">Tip.</strong>
    You don't need a local database — we provision an isolated Postgres
    on our managed cluster and give Asterisk read access automatically.
  </p>
</div>
"""
    + step(
        1,
        "Send us your public IP",
        f"""
<p style="margin:0 0 0.75rem 0;">Email
<a href="mailto:support@echodesk.ge" style="color:hsl(var(--primary));">support@echodesk.ge</a>
with the public IPv4 address of your Asterisk server. We add it to our
database firewall.</p>
<div style="{ALERT_WARN_STYLE}">
  <p style="margin:0;">
    <strong style="color:hsl(38 92% 45%);">Heads up.</strong>
    Do this <em>before</em> step&nbsp;2 — otherwise the install script
    will hang trying to reach the database and Asterisk systemd will
    time out after 5 minutes.
  </p>
</div>
""",
    )
    + step(
        2,
        "Register your PBX in EchoDesk",
        f"""
<ol style="margin:0;padding-left:1.25rem;">
  <li style="margin-bottom:0.375rem;">Sign in as a <strong>tenant admin</strong>.</li>
  <li style="margin-bottom:0.375rem;">Go to <strong>Settings → PBX → PBX Server</strong> ({ic("/settings/pbx/server/")}).</li>
  <li style="margin-bottom:0.375rem;">Click <strong>Connect your PBX</strong> and fill in:
    <ul style="margin:0.375rem 0 0 1rem;padding:0;">
      <li><strong>Name</strong> — any label (e.g. "Main PBX").</li>
      <li><strong>FQDN</strong> — the domain name of your Asterisk.</li>
      <li><strong>Public IP</strong> — same address you emailed support.</li>
      <li><strong>AMI port</strong> — leave {ic("5038")} unless you've changed it.</li>
    </ul>
  </li>
  <li>Click <strong>Save</strong>.</li>
</ol>
<p style="margin:0.75rem 0 0 0;">Behind the scenes EchoDesk creates your
isolated Postgres database, provisions a dedicated read-write role,
runs the realtime schema migration, and displays the install command.</p>
""",
    )
    + step(
        3,
        "Run the install script on your Asterisk",
        f"""
<p style="margin:0 0 0.5rem 0;">SSH into your Asterisk server as root
and paste the command from the UI:</p>
{code("curl -sSL https://api.echodesk.ge/api/pbx/install/&lt;token&gt;/ | sudo bash")}
<p style="margin:0.75rem 0;">The <strong>Copy</strong> button embeds the
token already. The script takes 30–60 seconds and will:</p>
<ul style="margin:0;padding-left:1.25rem;">
  <li style="margin-bottom:0.25rem;">Write {ic("/etc/asterisk/res_pgsql.conf")} with your DB credentials.</li>
  <li style="margin-bottom:0.25rem;">Append realtime mappings to {ic("sorcery.conf")} + {ic("extconfig.conf")}.</li>
  <li style="margin-bottom:0.25rem;">Preload {ic("res_config_pgsql.so")} in {ic("modules.conf")}.</li>
  <li style="margin-bottom:0.25rem;">Set {ic("PGSSLMODE=require")} via a systemd drop-in.</li>
  <li style="margin-bottom:0.25rem;">Install an AMI user at {ic("/etc/asterisk/manager.d/echodesk.conf")}.</li>
  <li>Restart Asterisk and ping back to EchoDesk with its version.</li>
</ul>
<div style="{NOTE_STYLE}">
  <strong>Safe to re-run.</strong> Every config file is backed up with a
  {ic(".bak.YYYYMMDD-HHMMSS")} suffix before the script touches it, so
  you can roll back at any time. The install script does
  <strong>not</strong> touch {ic("extensions.conf")} — that's yours.
</div>
""",
    )
    + step(
        4,
        "Verify the connection",
        (
            '<p style="margin:0 0 0.5rem 0;">Refresh <strong>Settings → PBX → PBX '
            'Server</strong>. You should see a green <strong>Active</strong> status '
            'badge and a fresh <strong>Last seen</strong> timestamp.</p>'
            '<p style="margin:0.75rem 0 0.5rem 0;">On your Asterisk server, confirm:</p>'
            + code(
                "# Database connection\n"
                "asterisk -rx 'realtime show pgsql status'\n"
                "# → Connected to asterisk_&lt;you&gt;@...d.db.ondigitalocean.com for N seconds\n"
                "\n"
                "# Endpoint list (empty at this point — no extensions yet)\n"
                "asterisk -rx 'pjsip show endpoints'"
            )
        ),
    )
    + step(
        5,
        "Add your first extension",
        f"""
<ol style="margin:0;padding-left:1.25rem;">
  <li style="margin-bottom:0.5rem;"><strong>Settings → PBX → Extensions</strong>, pick a user, assign an extension number + password.</li>
  <li style="margin-bottom:0.5rem;">On your Asterisk, within a few seconds:
    {code("asterisk -rx 'pjsip show endpoint 100'")}
    shows the endpoint with {ic("(realtime)")} next to its source.
  </li>
  <li>Configure a softphone with:
    <div style="{CARD_STYLE}margin-top:0.5rem;">
      <div style="display:grid;grid-template-columns:auto 1fr;gap:0.25rem 1rem;font-size:0.875rem;">
        <span style="font-weight:600;color:hsl(var(--foreground));">SIP server</span><span style="color:hsl(var(--muted-foreground));">your FQDN</span>
        <span style="font-weight:600;color:hsl(var(--foreground));">WebSocket URI</span><span style="color:hsl(var(--muted-foreground));font-family:monospace;font-size:0.8125rem;">wss://&lt;your-fqdn&gt;:8089/ws</span>
        <span style="font-weight:600;color:hsl(var(--foreground));">Username</span><span style="color:hsl(var(--muted-foreground));">the extension number</span>
        <span style="font-weight:600;color:hsl(var(--foreground));">Password</span><span style="color:hsl(var(--muted-foreground));">from the UI</span>
        <span style="font-weight:600;color:hsl(var(--foreground));">Transport</span><span style="color:hsl(var(--muted-foreground));">WSS</span>
      </div>
    </div>
  </li>
</ol>
""",
    )
    + step(
        6,
        "Wire up your dialplan (extensions.conf)",
        f"""
<p style="margin:0 0 0.75rem 0;">EchoDesk writes PJSIP endpoint
<em>configuration</em> into your realtime DB, but the <strong>dialplan</strong>
(what happens when a call hits a context) lives in
{ic("/etc/asterisk/extensions.conf")} on your server. The endpoints we
sync point at <strong>per-tenant context names</strong> that must exist
in your dialplan or every call gets rejected.</p>

<p style="margin:0 0 0.5rem 0;">For a tenant with schema {ic("acme")},
the agent endpoints are configured with {ic("context = tenant_acme")}
and the trunk endpoint with {ic("context = from-provider-acme")}. The
simplest dialplan is one that aliases each per-tenant name to your real
routing logic via {ic("include")}:</p>

{DIALPLAN_EXAMPLE_EN}

<p style="margin:0.75rem 0 0.5rem 0;">After editing, reload the
dialplan (no restart needed):</p>
{code("asterisk -rx 'dialplan reload'")}

<div style="{ALERT_WARN_STYLE}">
  <p style="margin:0;">
    <strong style="color:hsl(38 92% 45%);">If the per-tenant aliases are
    missing</strong>, every call logs in
    {ic("/var/log/asterisk/messages")} as
    <em>"extension 's' rejected because extension not found in context
    'from-provider-&lt;schema&gt;'"</em> (inbound) or the dialled number
    rejected in {ic("tenant_&lt;schema&gt;")} (outbound). That's the
    fingerprint to look for.
  </p>
</div>

<div style="{NOTE_STYLE}">
  <strong>Find your tenant schema name</strong> at
  <strong>Settings → General</strong>, or pull it from the subdomain
  on your dashboard URL ({ic("schema.echodesk.ge")}).
</div>
""",
    )
    + f"""
<h2 style="margin-top:3rem;">Troubleshooting</h2>
<p>The most common failure modes — click to expand the one that
matches your symptom.</p>

<details class="not-prose" style="{DETAILS_STYLE}">
  <summary style="{SUMMARY_STYLE}">Calls rejected: "extension not found in context tenant_&lt;schema&gt;"</summary>
  <div style="padding:0 1.25rem 1.25rem 1.25rem;font-size:0.875rem;color:hsl(var(--muted-foreground));">
    <p style="margin:0 0 0.5rem 0;">The per-tenant alias contexts in
    {ic("extensions.conf")} are missing. Add the four lines from
    Step 6 (with your schema substituted) and reload the dialplan.
    Check that the contexts exist with:</p>
    {code("asterisk -rx 'dialplan show tenant_&lt;your-schema&gt;'")}
  </div>
</details>

<details class="not-prose" style="{DETAILS_STYLE}">
  <summary style="{SUMMARY_STYLE}">Call connects then drops within 1 second (codec mismatch)</summary>
  <div style="padding:0 1.25rem 1.25rem 1.25rem;font-size:0.875rem;color:hsl(var(--muted-foreground));">
    <p style="margin:0 0 0.5rem 0;">Your trunk speaks classic codecs
    ({ic("ulaw")} / {ic("alaw")} / {ic("g722")}) but the WebRTC softphone
    only offered {ic("opus")}, and your Asterisk doesn't have
    {ic("codec_opus.so")} installed. {ic("/var/log/asterisk/messages")}
    shows:</p>
    {_CODEC_LOG_BLOCK}
    <p style="margin:0.75rem 0 0.25rem 0;"><strong>Fix:</strong> EchoDesk
    no longer adds Opus to the WebRTC endpoint allow-list (commit
    2d3b03d, 2026-04-26). If you registered before that, resync your PBX
    config from the dashboard, or contact support to re-run
    {ic("sync_tenant_asterisk")} for your schema.</p>
    <p style="margin:0.5rem 0 0 0;">Alternatively, install
    {ic("codec_opus.so")} so Asterisk can transcode — but the resync is
    simpler and avoids needing Opus codec licenses on your server.</p>
  </div>
</details>

<details class="not-prose" style="{DETAILS_STYLE}">
  <summary style="{SUMMARY_STYLE}">Inbound caller display shows the agent's own extension instead of the phone number</summary>
  <div style="padding:0 1.25rem 1.25rem 1.25rem;font-size:0.875rem;color:hsl(var(--muted-foreground));">
    <p style="margin:0 0 0.5rem 0;">A legacy version of the sync set
    {ic("from_user = &lt;extension&gt;")} on each WebRTC endpoint, which
    forces the From URI's user portion on every INVITE. Browser
    softphones display that, so an inbound call labelled "+995…" shows
    up as "101" in the agent's dashboard.</p>
    <p style="margin:0 0 0.25rem 0;"><strong>Fix:</strong> commit
    2fcb697 (2026-04-26) stops setting {ic("from_user")} on WebRTC
    endpoints. Resync your PBX config from the dashboard. To verify on
    your Asterisk:</p>
    {_FROM_USER_VERIFY_BLOCK}
    <p style="margin:0.5rem 0 0 0;">The line should be empty. If it
    still shows your extension number, the realtime row needs to be
    cleared — contact support.</p>
  </div>
</details>

<details class="not-prose" style="{DETAILS_STYLE}">
  <summary style="{SUMMARY_STYLE}">Install returns "Invalid or expired enrollment token"</summary>
  <div style="padding:0 1.25rem 1.25rem 1.25rem;font-size:0.875rem;color:hsl(var(--muted-foreground));">
    <p style="margin:0;">Tokens expire 24 hours after they're minted.
    In the UI click <strong>Regenerate install token</strong> and rerun
    the command.</p>
  </div>
</details>

<details class="not-prose" style="{DETAILS_STYLE}">
  <summary style="{SUMMARY_STYLE}">Status stays on "Awaiting install" after running the script</summary>
  <div style="padding:0 1.25rem 1.25rem 1.25rem;font-size:0.875rem;color:hsl(var(--muted-foreground));">
    <p style="margin:0 0 0.5rem 0;">The final step posts back to
    {ic("api.echodesk.ge")}. Outbound HTTPS on port 443 from your
    Asterisk is required.</p>
    {code("curl -v https://api.echodesk.ge/api/pbx/install/&lt;token&gt;/")}
  </div>
</details>

<details class="not-prose" style="{DETAILS_STYLE}">
  <summary style="{SUMMARY_STYLE}">"Not connected" in realtime show pgsql status</summary>
  <div style="padding:0 1.25rem 1.25rem 1.25rem;font-size:0.875rem;color:hsl(var(--muted-foreground));">
    <ol style="margin:0;padding-left:1.25rem;">
      <li style="margin-bottom:0.25rem;">Your public IP must be on our database firewall — email support if it changed.</li>
      <li style="margin-bottom:0.25rem;">Outbound port <strong>25060/tcp</strong> must be open from your server.</li>
      <li>If credentials drifted, click <strong>Regenerate install token</strong> and rerun the install script.</li>
    </ol>
  </div>
</details>

<details class="not-prose" style="{DETAILS_STYLE}">
  <summary style="{SUMMARY_STYLE}">Softphones won't register over WebSocket</summary>
  <div style="padding:0 1.25rem 1.25rem 1.25rem;font-size:0.875rem;color:hsl(var(--muted-foreground));">
    <p style="margin:0 0 0.5rem 0;">Your TLS cert chain must be valid —
    browsers refuse self-signed.</p>
    {code("openssl s_client -connect &lt;your-fqdn&gt;:8089")}
  </div>
</details>

<h2 style="margin-top:3rem;">Rolling back</h2>
<p>If you need to disconnect from EchoDesk — the install script kept
timestamped backups of every file it touched:</p>
""" + code(
        "cd /etc/asterisk\n"
        "for f in res_pgsql.conf sorcery.conf extconfig.conf modules.conf; do\n"
        "  BAK=$(ls -t $f.bak.* 2&gt;/dev/null | head -1)\n"
        "  [ -n \"$BAK\" ] &amp;&amp; cp \"$BAK\" $f\n"
        "done\n"
        "rm -f /etc/systemd/system/asterisk.service.d/echodesk.conf\n"
        "systemctl daemon-reload\n"
        "systemctl restart asterisk"
    ) + f"""
<p>Then delete the PBX Server entry in the EchoDesk UI. Your realtime
database stays around in case you want to reconnect later — contact
support to delete it permanently.</p>

<h2 style="margin-top:3rem;">What EchoDesk does not do</h2>
<div class="not-prose" style="display:grid;gap:0.5rem;grid-template-columns:repeat(2, minmax(0, 1fr));margin:1rem 0;">
  <div style="{NOTE_STYLE}margin:0;">
    <p style="font-weight:600;margin:0 0 0.25rem 0;color:hsl(var(--foreground));">No Asterisk installs</p>
    <p style="margin:0;color:hsl(var(--muted-foreground));">We don't install or upgrade Asterisk on your server.</p>
  </div>
  <div style="{NOTE_STYLE}margin:0;">
    <p style="font-weight:600;margin:0 0 0.25rem 0;color:hsl(var(--foreground));">No SIP provider setup</p>
    <p style="margin:0;color:hsl(var(--muted-foreground));">You enter provider credentials in the <strong>Trunks</strong> tab yourself.</p>
  </div>
  <div style="{NOTE_STYLE}margin:0;">
    <p style="font-weight:600;margin:0 0 0.25rem 0;color:hsl(var(--foreground));">No dialplan generation</p>
    <p style="margin:0;color:hsl(var(--muted-foreground));">Your routing logic in {ic("extensions.conf")} is yours to write — see Step 6.</p>
  </div>
  <div style="{NOTE_STYLE}margin:0;">
    <p style="font-weight:600;margin:0 0 0.25rem 0;color:hsl(var(--foreground));">No SSH access</p>
    <p style="margin:0;color:hsl(var(--muted-foreground));">The install script runs only when you invoke it — we never log in.</p>
  </div>
</div>
"""
)


# --- Georgian (condensed) --------------------------------------------------

DIALPLAN_EXAMPLE_KA = code(
    "; --- ტენანტისთვის specific contexts ---\n"
    "; &lt;your-schema&gt;-ის მაგივრად ჩაწერეთ თქვენი სქემა (მაგ. acme).\n"
    "[from-provider-&lt;your-schema&gt;]\n"
    "include =&gt; from-provider\n"
    "\n"
    "[tenant_&lt;your-schema&gt;]\n"
    "include =&gt; from-internal\n"
)


HERO_KA = f"""
<div class="not-prose" style="{HERO_STYLE}">
  <div style="margin-bottom:1rem;">
    <span style="{PILL_BASE}background:hsl(var(--primary));color:hsl(var(--primary-foreground));">თვით-მომსახურება</span>
    <span style="{PILL_BASE}background:color-mix(in srgb, hsl(142 71% 45%) 18%, transparent);color:hsl(142 71% 40%);">~10 წუთი</span>
    <span style="{PILL_BASE}background:color-mix(in srgb, hsl(217 91% 60%) 18%, transparent);color:hsl(217 91% 60%);">Asterisk 18+</span>
  </div>
  <p style="font-size:1rem;color:hsl(var(--foreground));line-height:1.65;margin:0;">
    დააკავშირეთ საკუთარი Asterisk და მართეთ <strong>ხაზები</strong>,
    <strong>რიგები</strong>, <strong>ტრანკები</strong> და
    <strong>შემოსული მარშრუტები</strong> EchoDesk-ის ადმინ პანელიდან.
    PJSIP კონფიგი realtime DB-ში წერია, ხოლო {ic("extensions.conf")} (dialplan)
    თქვენ კონტროლდება — ერთხელ უნდა დააკონფიგურიროთ ამ სტატიის Step 6-ით.
  </p>
</div>
"""

REQUIREMENTS_KA = f"""
<div class="not-prose" style="display:grid;gap:0.75rem;grid-template-columns:repeat(2, minmax(0, 1fr));margin:1.5rem 0;">
  {req_card("A", "Asterisk 18+", "Linux სერვერზე. EchoDesk იყენებს realtime დრაივერს.")}
  {req_card("B", "საჯარო FQDN + TLS", "მაგ. pbx.company.com. Let's Encrypt საკმარისია.")}
  {req_card("C", "გამავალი 25060/tcp", "Asterisk-ის realtime DB კავშირისთვის.")}
  {req_card("D", "შემომავალი 8089/tcp", "Softphone რეგისტრაციისთვის.")}
  {req_card("E", "Root/sudo წვდომა", "სკრიპტი წერს /etc/asterisk/-ში.")}
  {req_card("F", "DB ლოკალურად არ სჭირდება", "თქვენი realtime DB ჩვენს managed Postgres-ზე იქნება.")}
</div>
"""

CONTENT_KA = (
    HERO_KA
    + "<h2>სანამ დაიწყებთ</h2>"
    + REQUIREMENTS_KA
    + step(
        1,
        "გამოგვიგზავნეთ საჯარო IP",
        f"""
<p style="margin:0 0 0.75rem 0;">დაწერეთ
<a href="mailto:support@echodesk.ge" style="color:hsl(var(--primary));">support@echodesk.ge</a>-ზე
თქვენი Asterisk-ის საჯარო IPv4.</p>
<div style="{ALERT_WARN_STYLE}">
  <p style="margin:0;">
    <strong style="color:hsl(38 92% 45%);">ყურადღება.</strong>
    ეს გააკეთეთ <em>ნაბიჯ 2-მდე</em>.
  </p>
</div>
""",
    )
    + step(
        2,
        "დაარეგისტრირეთ PBX EchoDesk-ში",
        """
<ol style="margin:0;padding-left:1.25rem;">
  <li style="margin-bottom:0.375rem;">შედით ტენანტის ადმინად.</li>
  <li style="margin-bottom:0.375rem;">გადადით <strong>პარამეტრები → PBX → PBX სერვერი</strong>-ზე.</li>
  <li style="margin-bottom:0.375rem;">დააჭირეთ <strong>დააკავშირეთ PBX</strong>-ს და შეავსეთ სახელი, FQDN, საჯარო IP.</li>
  <li>შეინახეთ.</li>
</ol>
""",
    )
    + step(
        3,
        "გაუშვით ინსტალაციის ბრძანება",
        f"""
<p style="margin:0 0 0.5rem 0;">SSH-ით Asterisk სერვერზე root-ად:</p>
{code("curl -sSL https://api.echodesk.ge/api/pbx/install/&lt;token&gt;/ | sudo bash")}
<p style="margin:0.75rem 0 0 0;">30–60 წამში. ძველი კონფიგი დაცულია
{ic(".bak.*")} ფაილებში. {ic("extensions.conf")}-ს სკრიპტი
<strong>არ ცვლის</strong> — Step 6-ში გჭირდებათ ხელით.</p>
""",
    )
    + step(
        4,
        "შემოწმება",
        code("""asterisk -rx 'realtime show pgsql status'
asterisk -rx 'pjsip show endpoints'""")
        + '<p style="margin:0.75rem 0 0 0;">UI-ში უნდა აჩვენოს მწვანე <strong>Active</strong>.</p>',
    )
    + step(
        5,
        "პირველი ხაზის დამატება",
        f"""
<p style="margin:0;"><strong>პარამეტრები → PBX → ხაზები</strong> → აირჩიეთ
მომხმარებელი → ნომერი + პაროლი. Softphone რეგისტრირდება WSS-ით:
{ic("wss://&lt;fqdn&gt;:8089/ws")}.</p>
""",
    )
    + step(
        6,
        "Dialplan-ის კონფიგურაცია (extensions.conf)",
        f"""
<p style="margin:0 0 0.75rem 0;">EchoDesk PJSIP endpoint-ებს ტენანტ-სპეციფიკურ
context-ებზე უგზავნის ({ic("tenant_&lt;schema&gt;")} და
{ic("from-provider-&lt;schema&gt;")}). თქვენი
{ic("/etc/asterisk/extensions.conf")}-ში ეს context-ები აუცილებლად უნდა
იყოს, წინააღმდეგ შემთხვევაში ყველა ზარი დაიხურება.</p>

{DIALPLAN_EXAMPLE_KA}

<p style="margin:0.75rem 0 0 0;">შემდეგ ჩატვირთეთ dialplan-ი:</p>
{code("asterisk -rx 'dialplan reload'")}

<div style="{NOTE_STYLE}">
  <strong>თქვენი schema-ს სახელი</strong> — Settings → General-ში ან
  dashboard-ის subdomain-ში ({ic("schema.echodesk.ge")}).
</div>
""",
    )
    + f"""
<h2 style="margin-top:3rem;">პრობლემების მოგვარება</h2>

<details class="not-prose" style="{DETAILS_STYLE}">
  <summary style="{SUMMARY_STYLE}">"extension not found in context tenant_&lt;schema&gt;"</summary>
  <div style="padding:0 1.25rem 1.25rem 1.25rem;font-size:0.875rem;color:hsl(var(--muted-foreground));">
    <p style="margin:0;">{ic("extensions.conf")}-ში per-tenant alias context-ები არ არის. დაამატეთ Step 6-ის ხაზები.</p>
  </div>
</details>

<details class="not-prose" style="{DETAILS_STYLE}">
  <summary style="{SUMMARY_STYLE}">ზარი იწყება და მაშინვე იხურება (codec-ის შეუთავსებლობა)</summary>
  <div style="padding:0 1.25rem 1.25rem 1.25rem;font-size:0.875rem;color:hsl(var(--muted-foreground));">
    <p style="margin:0;">ბრაუზერი Opus-ს იყენებდა, ხოლო ტრანკი ulaw/alaw-ს. EchoDesk-ის ახალ კონფიგში Opus გამორთულია — Resync დაგჭირდებათ dashboard-დან.</p>
  </div>
</details>

<details class="not-prose" style="{DETAILS_STYLE}">
  <summary style="{SUMMARY_STYLE}">ნომრის ნაცვლად ჩანს ხაზის ნომერი</summary>
  <div style="padding:0 1.25rem 1.25rem 1.25rem;font-size:0.875rem;color:hsl(var(--muted-foreground));">
    <p style="margin:0;">ძველ კონფიგში endpoint-ს {ic("from_user")} ჰქონდა მითითებული. ახალ ვერსიაში ეს მოიხსნა — Resync-ის შემდეგ მუშაობს.</p>
  </div>
</details>

<details class="not-prose" style="{DETAILS_STYLE}">
  <summary style="{SUMMARY_STYLE}">ტოკენი ამოიწურა</summary>
  <div style="padding:0 1.25rem 1.25rem 1.25rem;font-size:0.875rem;color:hsl(var(--muted-foreground));">
    <p style="margin:0;">UI-ში დააჭირეთ <strong>ტოკენის განახლებას</strong>.</p>
  </div>
</details>

<p style="font-size:0.875rem;color:hsl(var(--muted-foreground));margin-top:1.5rem;">სრული
ინგლისურენოვანი გაიდი ხელმისაწვდომია ამავე სტატიის English ვერსიაში.</p>
"""
)


# --- Russian (condensed) ---------------------------------------------------

DIALPLAN_EXAMPLE_RU = code(
    "; --- Контексты для тенанта ---\n"
    "; Замените &lt;your-schema&gt; на ваш слаг (например acme).\n"
    "[from-provider-&lt;your-schema&gt;]\n"
    "include =&gt; from-provider\n"
    "\n"
    "[tenant_&lt;your-schema&gt;]\n"
    "include =&gt; from-internal\n"
)

HERO_RU = f"""
<div class="not-prose" style="{HERO_STYLE}">
  <div style="margin-bottom:1rem;">
    <span style="{PILL_BASE}background:hsl(var(--primary));color:hsl(var(--primary-foreground));">Самостоятельно</span>
    <span style="{PILL_BASE}background:color-mix(in srgb, hsl(142 71% 45%) 18%, transparent);color:hsl(142 71% 40%);">~10 мин</span>
    <span style="{PILL_BASE}background:color-mix(in srgb, hsl(217 91% 60%) 18%, transparent);color:hsl(217 91% 60%);">Asterisk 18+</span>
  </div>
  <p style="font-size:1rem;color:hsl(var(--foreground));line-height:1.65;margin:0;">
    Подключите свой Asterisk и управляйте <strong>расширениями</strong>,
    <strong>очередями</strong>, <strong>транками</strong> и <strong>входящей маршрутизацией</strong>
    из EchoDesk. PJSIP конфиг живёт в realtime БД, а
    {ic("extensions.conf")} (dialplan) — за вами; настраивается один раз
    по шагу 6.
  </p>
</div>
"""

REQUIREMENTS_RU = f"""
<div class="not-prose" style="display:grid;gap:0.75rem;grid-template-columns:repeat(2, minmax(0, 1fr));margin:1.5rem 0;">
  {req_card("A", "Asterisk 18+", "На Linux-сервере. realtime-драйвер.")}
  {req_card("B", "Публичный FQDN + TLS", "например pbx.company.com. Let's Encrypt подойдёт.")}
  {req_card("C", "Исходящий 25060/tcp", "Для Asterisk → managed Postgres.")}
  {req_card("D", "Входящий 8089/tcp", "Для регистрации softphone.")}
  {req_card("E", "Root / sudo", "Скрипт пишет в /etc/asterisk/.")}
  {req_card("F", "БД не нужна локально", "realtime БД хостим мы.")}
</div>
"""

CONTENT_RU = (
    HERO_RU
    + "<h2>Перед началом</h2>"
    + REQUIREMENTS_RU
    + step(
        1,
        "Пришлите нам публичный IP",
        f"""
<p style="margin:0 0 0.75rem 0;">Напишите на
<a href="mailto:support@echodesk.ge" style="color:hsl(var(--primary));">support@echodesk.ge</a>
публичный IPv4 вашего Asterisk.</p>
<div style="{ALERT_WARN_STYLE}">
  <p style="margin:0;">
    <strong style="color:hsl(38 92% 45%);">Важно.</strong>
    До шага 2.
  </p>
</div>
""",
    )
    + step(
        2,
        "Зарегистрируйте PBX в EchoDesk",
        """
<ol style="margin:0;padding-left:1.25rem;">
  <li style="margin-bottom:0.375rem;">Войдите как администратор тенанта.</li>
  <li style="margin-bottom:0.375rem;">Откройте <strong>Настройки → PBX → PBX Сервер</strong>.</li>
  <li style="margin-bottom:0.375rem;">Нажмите <strong>Подключить PBX</strong>, заполните имя, FQDN, публичный IP.</li>
  <li>Сохраните.</li>
</ol>
""",
    )
    + step(
        3,
        "Запустите скрипт установки",
        code("curl -sSL https://api.echodesk.ge/api/pbx/install/&lt;token&gt;/ | sudo bash")
        + f'<p style="margin:0.75rem 0 0 0;">30–60 секунд. Резервные копии в {ic(".bak.*")}. {ic("extensions.conf")} <strong>не</strong> трогаем — настраивается в шаге 6.</p>',
    )
    + step(
        4,
        "Проверка",
        code("""asterisk -rx 'realtime show pgsql status'
asterisk -rx 'pjsip show endpoints'""")
        + '<p style="margin:0.75rem 0 0 0;">В UI должен загореться зелёный <strong>Active</strong>.</p>',
    )
    + step(
        5,
        "Первое расширение",
        f"""
<p style="margin:0;"><strong>Настройки → PBX → Расширения</strong> →
выберите пользователя → номер и пароль. Softphone регистрируется по WSS:
{ic("wss://&lt;fqdn&gt;:8089/ws")}.</p>
""",
    )
    + step(
        6,
        "Настройка dialplan (extensions.conf)",
        f"""
<p style="margin:0 0 0.75rem 0;">EchoDesk пишет в realtime БД endpoint-ы с
контекстами {ic("tenant_&lt;schema&gt;")} и
{ic("from-provider-&lt;schema&gt;")}. Эти контексты <strong>обязаны</strong>
существовать в вашем {ic("/etc/asterisk/extensions.conf")}, иначе все
звонки будут отклоняться.</p>

{DIALPLAN_EXAMPLE_RU}

<p style="margin:0.75rem 0 0 0;">Перезагрузите dialplan:</p>
{code("asterisk -rx 'dialplan reload'")}

<div style="{NOTE_STYLE}">
  <strong>Имя schema</strong> — в Settings → General или в субдомене
  ({ic("schema.echodesk.ge")}).
</div>
""",
    )
    + f"""
<h2 style="margin-top:3rem;">Диагностика</h2>

<details class="not-prose" style="{DETAILS_STYLE}">
  <summary style="{SUMMARY_STYLE}">"extension not found in context tenant_&lt;schema&gt;"</summary>
  <div style="padding:0 1.25rem 1.25rem 1.25rem;font-size:0.875rem;color:hsl(var(--muted-foreground));">
    <p style="margin:0;">Не хватает alias-контекстов в {ic("extensions.conf")}. Добавьте по шагу 6.</p>
  </div>
</details>

<details class="not-prose" style="{DETAILS_STYLE}">
  <summary style="{SUMMARY_STYLE}">Звонок соединяется и падает за секунду (codec mismatch)</summary>
  <div style="padding:0 1.25rem 1.25rem 1.25rem;font-size:0.875rem;color:hsl(var(--muted-foreground));">
    <p style="margin:0;">Браузер использовал Opus, транк — ulaw. В новом конфиге EchoDesk Opus отключён — нужен resync через dashboard.</p>
  </div>
</details>

<details class="not-prose" style="{DETAILS_STYLE}">
  <summary style="{SUMMARY_STYLE}">CallerID показывает номер расширения вместо реального номера</summary>
  <div style="padding:0 1.25rem 1.25rem 1.25rem;font-size:0.875rem;color:hsl(var(--muted-foreground));">
    <p style="margin:0;">В старой версии sync ставился {ic("from_user")} на endpoint. В новой — нет; resync исправит.</p>
  </div>
</details>

<details class="not-prose" style="{DETAILS_STYLE}">
  <summary style="{SUMMARY_STYLE}">Токен истёк</summary>
  <div style="padding:0 1.25rem 1.25rem 1.25rem;font-size:0.875rem;color:hsl(var(--muted-foreground));">
    <p style="margin:0;">Срок жизни — 24 часа. Нажмите <strong>Обновить токен</strong> в UI.</p>
  </div>
</details>

<p style="font-size:0.875rem;color:hsl(var(--muted-foreground));margin-top:1.5rem;">Полная
инструкция доступна в английской версии этой статьи.</p>
"""
)


def upsert_article(apps, schema_editor):
    HelpCategory = apps.get_model("help_center", "HelpCategory")
    HelpArticle = apps.get_model("help_center", "HelpArticle")

    category = HelpCategory.objects.filter(slug="pbx-setup").first()
    if category is None:
        return

    HelpArticle.objects.update_or_create(
        slug=ARTICLE_SLUG,
        defaults=dict(
            category=category,
            title=TITLE,
            summary=SUMMARY,
            content_type="article",
            content={"en": CONTENT_EN, "ka": CONTENT_KA, "ru": CONTENT_RU},
            position=10,
            is_active=True,
            is_featured=True,
            show_on_public=True,
            show_in_dashboard=True,
        ),
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("help_center", "0004_pbx_connect_article_inline_styles"),
    ]
    operations = [
        migrations.RunPython(upsert_article, noop_reverse),
    ]
