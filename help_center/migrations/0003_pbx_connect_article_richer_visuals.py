"""Upgrade the 'Connect your Asterisk' article with richer visual styling.

Replaces the plain HTML from 0002 with Tailwind-class decorated blocks:
numbered step cards, requirement grid, alert callouts, collapsible
troubleshooting, language-labelled code blocks. Relies on the fact
that ``ArticleContent`` wraps content in a ``prose`` container and
DOMPurify keeps ``class`` attributes + ``<details>/<summary>`` tags.

The ``not-prose`` wrapper opts subtrees out of Tailwind Typography's
default spacing so our custom cards look right.
"""
from django.db import migrations


ARTICLE_SLUG = "connect-your-asterisk"


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


# --- Reusable style snippets -------------------------------------------------
# Tailwind class strings are long; centralise them so the article body stays
# readable. The `prose` wrapper around the article applies default styling to
# bare tags; `not-prose` opts subtrees out so custom cards render correctly.

CARD = (
    "rounded-xl border border-border bg-card p-5 shadow-sm "
    "hover:shadow-md transition-shadow"
)
PILL = (
    "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs "
    "font-semibold"
)
STEP_CIRCLE = (
    "flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full "
    "bg-primary text-primary-foreground font-bold text-lg shadow-md"
)
ALERT_INFO = (
    "not-prose my-6 rounded-lg border-l-4 border-blue-500 bg-blue-50 "
    "dark:bg-blue-950/30 p-4 text-sm leading-relaxed"
)
ALERT_WARN = (
    "not-prose my-6 rounded-lg border-l-4 border-amber-500 bg-amber-50 "
    "dark:bg-amber-950/30 p-4 text-sm leading-relaxed"
)
ALERT_TIP = (
    "not-prose my-6 rounded-lg border-l-4 border-green-500 bg-green-50 "
    "dark:bg-green-950/30 p-4 text-sm leading-relaxed"
)


def step(number: int, title: str, body: str) -> str:
    """A numbered step block that visually mirrors StepByStepGuide."""
    return f"""
<div class="not-prose my-8 flex gap-4">
  <div class="{STEP_CIRCLE}">{number}</div>
  <div class="flex-1 pt-1 space-y-3">
    <h3 class="text-xl font-semibold text-foreground m-0">{title}</h3>
    <div class="text-sm text-muted-foreground leading-relaxed space-y-3">
      {body}
    </div>
  </div>
</div>
"""


def req_card(icon: str, label: str, detail: str) -> str:
    """One box in the requirements grid."""
    return f"""
<div class="{CARD}">
  <div class="flex items-start gap-3">
    <div class="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary font-bold">
      {icon}
    </div>
    <div class="space-y-1">
      <p class="font-semibold text-sm text-foreground m-0">{label}</p>
      <p class="text-xs text-muted-foreground m-0">{detail}</p>
    </div>
  </div>
</div>
"""


# --- English content ---------------------------------------------------------

HERO_EN = """
<div class="not-prose mb-10 rounded-2xl bg-gradient-to-br from-primary/10 via-primary/5 to-transparent p-8 border border-border">
  <div class="flex flex-wrap items-center gap-2 mb-4">
    <span class="inline-flex items-center rounded-full bg-primary text-primary-foreground px-3 py-1 text-xs font-semibold">Self-service</span>
    <span class="inline-flex items-center rounded-full bg-green-100 dark:bg-green-950/40 text-green-700 dark:text-green-400 px-3 py-1 text-xs font-semibold">~10 min setup</span>
    <span class="inline-flex items-center rounded-full bg-blue-100 dark:bg-blue-950/40 text-blue-700 dark:text-blue-400 px-3 py-1 text-xs font-semibold">Asterisk 18+</span>
  </div>
  <p class="text-base text-foreground leading-relaxed m-0">
    Bring your own Asterisk server and manage <strong>extensions</strong>,
    <strong>queues</strong>, <strong>trunks</strong> and <strong>inbound routing</strong>
    directly from the EchoDesk admin panel. Every change you make in the UI
    lands on your Asterisk within seconds — no SSH, no config edits,
    no <code class="px-1 py-0.5 rounded bg-muted text-primary text-xs">pjsip reload</code>.
  </p>
</div>
"""

REQUIREMENTS_EN = f"""
<div class="not-prose my-6 grid gap-3 sm:grid-cols-2">
  {req_card("A", "Asterisk 18 or newer", "On a Linux server you control. We talk to Asterisk via its realtime driver, which is standard in Asterisk 18+.")}
  {req_card("B", "Public FQDN + TLS cert", "e.g. pbx.mycompany.com. Let's Encrypt is fine — browsers refuse self-signed certs for WebSocket softphones.")}
  {req_card("C", "Outbound 25060/tcp", "For Asterisk's realtime DB connection to our managed Postgres cluster.")}
  {req_card("D", "Inbound 8089/tcp (WSS)", "So softphones can register. Plus your SIP provider's signalling port.")}
  {req_card("E", "Root / sudo access", "The install script writes under /etc/asterisk/ and adds a systemd drop-in.")}
  {req_card("F", "No database needed locally", "We host your realtime DB on our managed Postgres. You only provide the Asterisk server.")}
</div>
"""

CONTENT_EN = (
    HERO_EN
    + "<h2>Before you start</h2>"
    + REQUIREMENTS_EN
    + f"""
<div class="{ALERT_TIP}">
  <p class="m-0"><strong class="text-green-800 dark:text-green-300">Tip.</strong>
  You don't need to install a database on your Asterisk server — we
  provision an isolated Postgres database for you on our managed
  cluster and give Asterisk read access to it automatically.</p>
</div>
"""
    + step(
        1,
        "Send us your public IP",
        f"""
<p>Email <a href="mailto:support@echodesk.ge">support@echodesk.ge</a> with the
public IPv4 address of your Asterisk server. We add it to our database
firewall.</p>
<div class="{ALERT_WARN}">
  <p class="m-0"><strong class="text-amber-800 dark:text-amber-300">Heads up.</strong>
  Do this <em>before</em> step&nbsp;2. Otherwise the install script will
  hang trying to reach the database and Asterisk systemd will time out
  after 5 minutes.</p>
</div>
""",
    )
    + step(
        2,
        "Register your PBX in EchoDesk",
        """
<ol class="list-decimal ml-5 space-y-1">
  <li>Sign in as a <strong>tenant admin</strong>.</li>
  <li>Go to <strong>Settings → PBX → PBX Server</strong> (<code class="px-1 py-0.5 rounded bg-muted text-primary text-xs">/settings/pbx/server/</code>).</li>
  <li>Click <strong>Connect your PBX</strong> and fill in:
    <ul class="list-disc ml-5 mt-1 space-y-1">
      <li><strong>Name</strong> — any label (e.g. "Main PBX").</li>
      <li><strong>FQDN</strong> — the domain name of your Asterisk.</li>
      <li><strong>Public IP</strong> — same address you emailed support.</li>
      <li><strong>AMI port</strong> — leave <code class="px-1 py-0.5 rounded bg-muted text-primary text-xs">5038</code> unless you've changed it.</li>
    </ul>
  </li>
  <li>Click <strong>Save</strong>.</li>
</ol>
<p>Behind the scenes EchoDesk creates your isolated Postgres database,
provisions a dedicated read-write role, runs the realtime schema
migration, and displays the install command you'll run next.</p>
""",
    )
    + step(
        3,
        "Run the install script on your Asterisk",
        """
<p>SSH into your Asterisk server as root and paste the command from the
UI. It looks like this:</p>
<pre class="not-prose rounded-lg bg-zinc-900 text-zinc-100 p-4 text-xs overflow-x-auto"><code>curl -sSL https://api.echodesk.ge/api/pbx/install/&lt;token&gt;/ | sudo bash</code></pre>
<p>The <strong>Copy</strong> button in the UI already has the token
embedded. The script takes 30–60 seconds and will:</p>
<ul class="list-disc ml-5 space-y-1 marker:text-primary">
  <li>Write <code class="px-1 py-0.5 rounded bg-muted text-primary text-xs">/etc/asterisk/res_pgsql.conf</code> with your DB credentials.</li>
  <li>Append realtime mappings to <code class="px-1 py-0.5 rounded bg-muted text-primary text-xs">sorcery.conf</code> + <code class="px-1 py-0.5 rounded bg-muted text-primary text-xs">extconfig.conf</code>.</li>
  <li>Preload <code class="px-1 py-0.5 rounded bg-muted text-primary text-xs">res_config_pgsql.so</code> in <code class="px-1 py-0.5 rounded bg-muted text-primary text-xs">modules.conf</code>.</li>
  <li>Set <code class="px-1 py-0.5 rounded bg-muted text-primary text-xs">PGSSLMODE=require</code> via a systemd drop-in.</li>
  <li>Install an AMI user at <code class="px-1 py-0.5 rounded bg-muted text-primary text-xs">/etc/asterisk/manager.d/echodesk.conf</code>.</li>
  <li>Restart Asterisk and ping back to EchoDesk with its version.</li>
</ul>
<div class="not-prose my-4 rounded-lg border border-border bg-muted/40 p-3 text-xs">
  <strong>Safe to re-run.</strong> Every config file is backed up with a
  <code class="px-1 py-0.5 rounded bg-background text-primary">.bak.YYYYMMDD-HHMMSS</code>
  suffix before the script touches it, so you can roll back at any time.
</div>
""",
    )
    + step(
        4,
        "Verify the connection",
        """
<p>Refresh <strong>Settings → PBX → PBX Server</strong>. You should see:</p>
<ul class="list-disc ml-5 space-y-1 marker:text-primary">
  <li>A green <strong>Active</strong> status badge.</li>
  <li>A fresh <strong>Last seen</strong> timestamp.</li>
</ul>
<p>On your Asterisk server, confirm:</p>
<pre class="not-prose rounded-lg bg-zinc-900 text-zinc-100 p-4 text-xs overflow-x-auto"><code># Database connection
asterisk -rx 'realtime show pgsql status'
# → Connected to asterisk_&lt;you&gt;@...d.db.ondigitalocean.com for N seconds

# Endpoint list (empty at this point — no extensions yet)
asterisk -rx 'pjsip show endpoints'</code></pre>
""",
    )
    + step(
        5,
        "Add your first extension",
        """
<ol class="list-decimal ml-5 space-y-1">
  <li><strong>Settings → PBX → Extensions</strong>, pick a user, assign an extension number + password.</li>
  <li>On your Asterisk, within a few seconds:
    <pre class="not-prose rounded-lg bg-zinc-900 text-zinc-100 p-4 text-xs overflow-x-auto mt-2"><code>asterisk -rx 'pjsip show endpoint 100'</code></pre>
    shows the endpoint with <code class="px-1 py-0.5 rounded bg-muted text-primary text-xs">(realtime)</code> next to its source.
  </li>
  <li>Configure a softphone with:
    <div class="not-prose my-3 rounded-lg border border-border bg-card p-4 text-sm space-y-1">
      <div class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
        <span class="font-semibold text-foreground">SIP server</span><span class="text-muted-foreground">your FQDN</span>
        <span class="font-semibold text-foreground">WebSocket URI</span><span class="text-muted-foreground font-mono text-xs">wss://&lt;your-fqdn&gt;:8089/ws</span>
        <span class="font-semibold text-foreground">Username</span><span class="text-muted-foreground">the extension number</span>
        <span class="font-semibold text-foreground">Password</span><span class="text-muted-foreground">from the UI</span>
        <span class="font-semibold text-foreground">Transport</span><span class="text-muted-foreground">WSS</span>
      </div>
    </div>
  </li>
</ol>
""",
    )
    + """
<h2>Troubleshooting</h2>
<p>The four most common failure modes — click to expand the one that
matches your symptom.</p>

<details class="not-prose my-3 rounded-lg border border-border bg-card">
  <summary class="cursor-pointer select-none px-4 py-3 font-semibold text-sm hover:bg-muted/40 rounded-lg">
    Install returns "Invalid or expired enrollment token"
  </summary>
  <div class="px-4 pb-4 text-sm text-muted-foreground space-y-2">
    <p>Tokens expire 24 hours after they're minted. In the UI click
    <strong>Regenerate install token</strong> and rerun the command.</p>
  </div>
</details>

<details class="not-prose my-3 rounded-lg border border-border bg-card">
  <summary class="cursor-pointer select-none px-4 py-3 font-semibold text-sm hover:bg-muted/40 rounded-lg">
    Status stays on "Awaiting install" after running the script
  </summary>
  <div class="px-4 pb-4 text-sm text-muted-foreground space-y-2">
    <p>The final step of the script posts back to <code class="px-1 py-0.5 rounded bg-muted text-primary text-xs">api.echodesk.ge</code>. Outbound HTTPS on port 443 from your Asterisk is required.</p>
    <pre class="not-prose rounded-lg bg-zinc-900 text-zinc-100 p-3 text-xs overflow-x-auto"><code>curl -v https://api.echodesk.ge/api/pbx/install/&lt;token&gt;/</code></pre>
  </div>
</details>

<details class="not-prose my-3 rounded-lg border border-border bg-card">
  <summary class="cursor-pointer select-none px-4 py-3 font-semibold text-sm hover:bg-muted/40 rounded-lg">
    "Not connected" in <code>realtime show pgsql status</code>
  </summary>
  <div class="px-4 pb-4 text-sm text-muted-foreground space-y-2">
    <ol class="list-decimal ml-5 space-y-1">
      <li>Your public IP must be on our database firewall. If your IP changed, email support.</li>
      <li>Outbound port <strong>25060/tcp</strong> must be open from your server.</li>
      <li>If credentials drifted, click <strong>Regenerate install token</strong> and rerun the install script — it'll rewrite the DB config file.</li>
    </ol>
  </div>
</details>

<details class="not-prose my-3 rounded-lg border border-border bg-card">
  <summary class="cursor-pointer select-none px-4 py-3 font-semibold text-sm hover:bg-muted/40 rounded-lg">
    Softphones won't register over WebSocket
  </summary>
  <div class="px-4 pb-4 text-sm text-muted-foreground space-y-2">
    <p>Your TLS cert chain must be valid — browsers refuse self-signed.</p>
    <pre class="not-prose rounded-lg bg-zinc-900 text-zinc-100 p-3 text-xs overflow-x-auto"><code>openssl s_client -connect &lt;your-fqdn&gt;:8089</code></pre>
  </div>
</details>

<h2>Rolling back</h2>
<p>If you need to disconnect from EchoDesk — the install script kept
timestamped backups of every file it touched:</p>
<pre class="not-prose rounded-lg bg-zinc-900 text-zinc-100 p-4 text-xs overflow-x-auto"><code>cd /etc/asterisk
for f in res_pgsql.conf sorcery.conf extconfig.conf modules.conf; do
  BAK=$(ls -t $f.bak.* 2&gt;/dev/null | head -1)
  [ -n "$BAK" ] &amp;&amp; cp "$BAK" $f
done
rm -f /etc/systemd/system/asterisk.service.d/echodesk.conf
systemctl daemon-reload
systemctl restart asterisk</code></pre>
<p>Then delete the PBX Server entry in the EchoDesk UI. Your realtime
database stays around in case you want to reconnect later — contact
support to delete it permanently.</p>

<h2>What EchoDesk does not do</h2>
<div class="not-prose my-4 grid gap-2 sm:grid-cols-2">
  <div class="rounded-lg border border-border bg-muted/30 p-3 text-xs">
    <p class="font-semibold text-foreground m-0 mb-1">No Asterisk installs</p>
    <p class="text-muted-foreground m-0">We don't install or upgrade Asterisk on your server — that's your responsibility.</p>
  </div>
  <div class="rounded-lg border border-border bg-muted/30 p-3 text-xs">
    <p class="font-semibold text-foreground m-0 mb-1">No SIP provider setup</p>
    <p class="text-muted-foreground m-0">You enter provider credentials in the <strong>Trunks</strong> tab yourself.</p>
  </div>
  <div class="rounded-lg border border-border bg-muted/30 p-3 text-xs">
    <p class="font-semibold text-foreground m-0 mb-1">No recordings backup</p>
    <p class="text-muted-foreground m-0">Call recordings stay on your server unless you configure S3/Spaces.</p>
  </div>
  <div class="rounded-lg border border-border bg-muted/30 p-3 text-xs">
    <p class="font-semibold text-foreground m-0 mb-1">No SSH access</p>
    <p class="text-muted-foreground m-0">The install script runs only when you invoke it — we never log in.</p>
  </div>
</div>
"""
)


# --- Georgian content (same structure, localised copy) -----------------------

HERO_KA = """
<div class="not-prose mb-10 rounded-2xl bg-gradient-to-br from-primary/10 via-primary/5 to-transparent p-8 border border-border">
  <div class="flex flex-wrap items-center gap-2 mb-4">
    <span class="inline-flex items-center rounded-full bg-primary text-primary-foreground px-3 py-1 text-xs font-semibold">თვით-მომსახურება</span>
    <span class="inline-flex items-center rounded-full bg-green-100 dark:bg-green-950/40 text-green-700 dark:text-green-400 px-3 py-1 text-xs font-semibold">~10 წთ</span>
    <span class="inline-flex items-center rounded-full bg-blue-100 dark:bg-blue-950/40 text-blue-700 dark:text-blue-400 px-3 py-1 text-xs font-semibold">Asterisk 18+</span>
  </div>
  <p class="text-base text-foreground leading-relaxed m-0">
    დააკავშირეთ საკუთარი Asterisk სერვერი და მართეთ
    <strong>ხაზები</strong>, <strong>რიგები</strong>, <strong>ტრანკები</strong> და
    <strong>შემოსული მარშრუტები</strong> EchoDesk-ის ადმინ პანელიდან. UI-ში
    ცვლილება რამდენიმე წამში ხვდება თქვენს Asterisk-ს — SSH-ის გარეშე.
  </p>
</div>
"""

REQUIREMENTS_KA = f"""
<div class="not-prose my-6 grid gap-3 sm:grid-cols-2">
  {req_card("A", "Asterisk 18+", "Linux სერვერზე. EchoDesk იყენებს realtime დრაივერს, რომელიც სტანდარტია Asterisk 18-დან.")}
  {req_card("B", "საჯარო FQDN + TLS", "მაგ. pbx.company.com. Let's Encrypt საკმარისია — თვით-ხელმოწერილი სერტიფიკატი ბრაუზერმა არ მიიღოს.")}
  {req_card("C", "გამავალი 25060/tcp", "Asterisk-ის realtime DB კავშირისთვის ჩვენს managed Postgres-თან.")}
  {req_card("D", "შემომავალი 8089/tcp", "რომ softphone-ები შეძლებენ რეგისტრაციას. პლუს SIP პროვაიდერის პორტი.")}
  {req_card("E", "Root/sudo წვდომა", "ინსტალაციის სკრიპტი წერს /etc/asterisk/-ში და ამატებს systemd drop-in-ს.")}
  {req_card("F", "DB ლოკალურად არ სჭირდება", "თქვენი realtime DB ჩვენს managed Postgres-ზე იქნება. თქვენ მხოლოდ Asterisk გვაძლევთ.")}
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
<p>დაწერეთ <a href="mailto:support@echodesk.ge">support@echodesk.ge</a>-ზე
თქვენი Asterisk-ის საჯარო IPv4 მისამართი. დავამატებთ ჩვენს DB
firewall-ში.</p>
<div class="{ALERT_WARN}">
  <p class="m-0"><strong class="text-amber-800 dark:text-amber-300">ყურადღება.</strong>
  ეს გააკეთეთ <em>ნაბიჯ 2-მდე</em>. წინააღმდეგ შემთხვევაში
  ინსტალაცია დაელოდება DB-ს და Asterisk systemd 5 წუთში გათიშავს.</p>
</div>
""",
    )
    + step(
        2,
        "დაარეგისტრირეთ PBX EchoDesk-ში",
        """
<ol class="list-decimal ml-5 space-y-1">
  <li>შედით ტენანტის ადმინად.</li>
  <li>გადადით <strong>პარამეტრები → PBX → PBX სერვერი</strong>-ზე.</li>
  <li>დააჭირეთ <strong>დააკავშირეთ PBX</strong>-ს და შეავსეთ სახელი, FQDN, საჯარო IP.</li>
  <li>შეინახეთ.</li>
</ol>
<p>EchoDesk ქმნის იზოლირებულ Postgres DB-ს, ნიშნავს RW მომხმარებელს,
უშვებს schema მიგრაციას და გიჩვენებთ ინსტალაციის ბრძანებას.</p>
""",
    )
    + step(
        3,
        "გაუშვით ინსტალაციის ბრძანება",
        """
<p>SSH-ით Asterisk სერვერზე root-ად:</p>
<pre class="not-prose rounded-lg bg-zinc-900 text-zinc-100 p-4 text-xs overflow-x-auto"><code>curl -sSL https://api.echodesk.ge/api/pbx/install/&lt;token&gt;/ | sudo bash</code></pre>
<p>30–60 წამში დაიწერება res_pgsql.conf, sorcery/extconfig განახლდება, AMI
მომხმარებელი შექმნება, Asterisk გადაიტვირთება. ძველი კონფიგი დაცულია
<code class="px-1 py-0.5 rounded bg-muted text-primary text-xs">.bak.*</code> ფაილებში.</p>
""",
    )
    + step(
        4,
        "შემოწმება",
        """
<pre class="not-prose rounded-lg bg-zinc-900 text-zinc-100 p-4 text-xs overflow-x-auto"><code>asterisk -rx 'realtime show pgsql status'
asterisk -rx 'pjsip show endpoints'</code></pre>
<p>EchoDesk-ის UI უნდა აჩვენოს მწვანე <strong>Active</strong>.</p>
""",
    )
    + step(
        5,
        "პირველი ხაზის დამატება",
        """
<p><strong>პარამეტრები → PBX → ხაზები</strong> → აირჩიეთ მომხმარებელი →
ნომერი + პაროლი. Softphone რეგისტრირდება WSS-ით
(<code class="px-1 py-0.5 rounded bg-muted text-primary text-xs">wss://&lt;fqdn&gt;:8089/ws</code>).</p>
""",
    )
    + """
<h2>პრობლემების მოგვარება</h2>
<details class="not-prose my-3 rounded-lg border border-border bg-card">
  <summary class="cursor-pointer select-none px-4 py-3 font-semibold text-sm hover:bg-muted/40 rounded-lg">
    ტოკენი ამოიწურა
  </summary>
  <div class="px-4 pb-4 text-sm text-muted-foreground">
    <p>ტოკენი 24 საათის შემდეგ იშლება. UI-ში დააჭირეთ <strong>ტოკენის განახლებას</strong>.</p>
  </div>
</details>
<details class="not-prose my-3 rounded-lg border border-border bg-card">
  <summary class="cursor-pointer select-none px-4 py-3 font-semibold text-sm hover:bg-muted/40 rounded-lg">
    "Not connected" realtime show pgsql status-ში
  </summary>
  <div class="px-4 pb-4 text-sm text-muted-foreground">
    <p>შეამოწმეთ firewall და გამავალი პორტი 25060/tcp.</p>
  </div>
</details>

<p class="text-sm text-muted-foreground">სრული ინგლისურენოვანი გაიდი
ხელმისაწვდომია ამავე სტატიის English ვერსიაში.</p>
"""
)


# --- Russian content (same structure, localised copy) ------------------------

HERO_RU = """
<div class="not-prose mb-10 rounded-2xl bg-gradient-to-br from-primary/10 via-primary/5 to-transparent p-8 border border-border">
  <div class="flex flex-wrap items-center gap-2 mb-4">
    <span class="inline-flex items-center rounded-full bg-primary text-primary-foreground px-3 py-1 text-xs font-semibold">Самостоятельно</span>
    <span class="inline-flex items-center rounded-full bg-green-100 dark:bg-green-950/40 text-green-700 dark:text-green-400 px-3 py-1 text-xs font-semibold">~10 мин</span>
    <span class="inline-flex items-center rounded-full bg-blue-100 dark:bg-blue-950/40 text-blue-700 dark:text-blue-400 px-3 py-1 text-xs font-semibold">Asterisk 18+</span>
  </div>
  <p class="text-base text-foreground leading-relaxed m-0">
    Подключите собственный сервер Asterisk и управляйте
    <strong>расширениями</strong>, <strong>очередями</strong>,
    <strong>транками</strong> и <strong>входящей маршрутизацией</strong>
    прямо из панели EchoDesk. Любое изменение в UI доходит до Asterisk
    за секунды — без SSH и ручных правок.
  </p>
</div>
"""

REQUIREMENTS_RU = f"""
<div class="not-prose my-6 grid gap-3 sm:grid-cols-2">
  {req_card("A", "Asterisk 18+", "На Linux-сервере. Мы используем realtime-драйвер, стандартный с Asterisk 18.")}
  {req_card("B", "Публичный FQDN + TLS", "например pbx.company.com. Let's Encrypt подойдёт — браузеры отвергают самоподписанные.")}
  {req_card("C", "Исходящий 25060/tcp", "Для подключения Asterisk к нашей managed Postgres.")}
  {req_card("D", "Входящий 8089/tcp", "Чтобы softphone мог регистрироваться. Плюс порт вашего SIP-провайдера.")}
  {req_card("E", "Root / sudo", "Скрипт пишет в /etc/asterisk/ и добавляет systemd drop-in.")}
  {req_card("F", "БД не нужна локально", "Мы хостим realtime БД для вас. Вы предоставляете только сервер Asterisk.")}
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
<p>Напишите на <a href="mailto:support@echodesk.ge">support@echodesk.ge</a>
публичный IPv4-адрес вашего Asterisk — добавим в firewall базы данных.</p>
<div class="{ALERT_WARN}">
  <p class="m-0"><strong class="text-amber-800 dark:text-amber-300">Важно.</strong>
  Сделайте это <em>до</em> шага 2, иначе установка зависнет при
  попытке подключиться к БД.</p>
</div>
""",
    )
    + step(
        2,
        "Зарегистрируйте PBX в EchoDesk",
        """
<ol class="list-decimal ml-5 space-y-1">
  <li>Войдите как администратор тенанта.</li>
  <li>Откройте <strong>Настройки → PBX → PBX Сервер</strong>.</li>
  <li>Нажмите <strong>Подключить PBX</strong>, заполните имя, FQDN, публичный IP.</li>
  <li>Сохраните.</li>
</ol>
""",
    )
    + step(
        3,
        "Запустите скрипт установки",
        """
<pre class="not-prose rounded-lg bg-zinc-900 text-zinc-100 p-4 text-xs overflow-x-auto"><code>curl -sSL https://api.echodesk.ge/api/pbx/install/&lt;token&gt;/ | sudo bash</code></pre>
<p>30–60 секунд. Скрипт создаёт резервные копии <code class="px-1 py-0.5 rounded bg-muted text-primary text-xs">.bak.*</code> старых конфигов.</p>
""",
    )
    + step(
        4,
        "Проверка",
        """
<pre class="not-prose rounded-lg bg-zinc-900 text-zinc-100 p-4 text-xs overflow-x-auto"><code>asterisk -rx 'realtime show pgsql status'
asterisk -rx 'pjsip show endpoints'</code></pre>
<p>В UI EchoDesk должен загореться зелёный бейдж <strong>Active</strong>.</p>
""",
    )
    + step(
        5,
        "Первое расширение",
        """
<p><strong>Настройки → PBX → Расширения</strong> → выберите пользователя
→ номер и пароль. Softphone регистрируется по WSS:
<code class="px-1 py-0.5 rounded bg-muted text-primary text-xs">wss://&lt;fqdn&gt;:8089/ws</code>.</p>
""",
    )
    + """
<h2>Диагностика</h2>
<details class="not-prose my-3 rounded-lg border border-border bg-card">
  <summary class="cursor-pointer select-none px-4 py-3 font-semibold text-sm hover:bg-muted/40 rounded-lg">
    Токен истёк
  </summary>
  <div class="px-4 pb-4 text-sm text-muted-foreground">
    <p>Срок жизни токена — 24 часа. Нажмите <strong>Обновить токен</strong> в UI.</p>
  </div>
</details>
<details class="not-prose my-3 rounded-lg border border-border bg-card">
  <summary class="cursor-pointer select-none px-4 py-3 font-semibold text-sm hover:bg-muted/40 rounded-lg">
    "Not connected" в realtime show pgsql status
  </summary>
  <div class="px-4 pb-4 text-sm text-muted-foreground">
    <p>Проверьте firewall и исходящий порт 25060/tcp.</p>
  </div>
</details>

<p class="text-sm text-muted-foreground">Подробная инструкция
доступна в английской версии этой статьи.</p>
"""
)


def upsert_article(apps, schema_editor):
    HelpCategory = apps.get_model("help_center", "HelpCategory")
    HelpArticle = apps.get_model("help_center", "HelpArticle")

    category = HelpCategory.objects.filter(slug="pbx-setup").first()
    if category is None:
        return  # 0002 creates it; if missing something is off, bail cleanly

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
    # 0002's forward migration is the canonical content; nothing to undo here
    # that would break UX beyond reverting to the 0002 plain-HTML version.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("help_center", "0002_tenant_pbx_connect_article"),
    ]
    operations = [
        migrations.RunPython(upsert_article, noop_reverse),
    ]
