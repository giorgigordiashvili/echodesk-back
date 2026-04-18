"""Publish the 'Connect your Asterisk to EchoDesk' guide into the public
help center so it shows up at /docs.

Idempotent: updates the article if it already exists (recognised by slug),
otherwise inserts. Removing the article rolls back cleanly.
"""
from django.db import migrations


ARTICLE_SLUG = "connect-your-asterisk"
CATEGORY_SLUG = "pbx-setup"


TITLE = {
    "en": "Connect your Asterisk to EchoDesk",
    "ka": "დააკავშირეთ თქვენი Asterisk EchoDesk-თან",
    "ru": "Подключите Asterisk к EchoDesk",
}

SUMMARY = {
    "en": (
        "Bring your own Asterisk 18+ server and manage extensions, queues, "
        "trunks and inbound routing from the EchoDesk admin panel. Changes "
        "take effect in seconds — no SSH, no file edits, no reloads."
    ),
    "ka": (
        "დააკავშირეთ საკუთარი Asterisk 18+ სერვერი და მართეთ ხაზები, რიგები, "
        "ტრანკები და შემოსული ზარები EchoDesk-ის ადმინ პანელიდან."
    ),
    "ru": (
        "Подключите свой сервер Asterisk 18+ и управляйте расширениями, "
        "очередями, транками и входящей маршрутизацией из панели EchoDesk."
    ),
}


CONTENT_EN = """
<h2>Before you start</h2>
<p>You'll need all of these in place <em>before</em> clicking <strong>Connect your PBX</strong> in the UI:</p>
<table>
  <thead><tr><th>Requirement</th><th>Why</th></tr></thead>
  <tbody>
    <tr><td><strong>Asterisk 18 or newer</strong> on a Linux server you control</td><td>We talk to Asterisk via its realtime driver (<code>res_config_pgsql</code>), which is standard in Asterisk 18 and later. Earlier versions are unsupported.</td></tr>
    <tr><td><strong>A public FQDN</strong> pointed at your Asterisk (e.g. <code>pbx.mycompany.com</code>)</td><td>Needed for softphone WebSocket (<code>wss://FQDN:8089/ws</code>) and for providers to deliver DIDs.</td></tr>
    <tr><td><strong>A valid TLS certificate</strong> on that FQDN</td><td>Browsers refuse WebSocket connections to self-signed certs. Let's Encrypt works.</td></tr>
    <tr><td><strong>Outbound</strong> internet on port <strong>25060/tcp</strong></td><td>For Asterisk's realtime DB connection to our managed Postgres.</td></tr>
    <tr><td><strong>Inbound</strong> internet on <strong>8089/tcp</strong> (WSS) and your SIP port</td><td>So softphones and SIP providers can reach you.</td></tr>
    <tr><td>Root / sudo access to the Asterisk server</td><td>The install script writes under <code>/etc/asterisk/</code> and adds a systemd drop-in.</td></tr>
  </tbody>
</table>
<p>You do <strong>not</strong> need to install a database on your server — we host your realtime DB on our managed Postgres cluster.</p>

<h2>1. Send us your public IP</h2>
<p>Email <a href="mailto:support@echodesk.ge">support@echodesk.ge</a> with the public IPv4 address of your Asterisk server. We'll add it to our database firewall. Do this <strong>before</strong> step 2 — otherwise the install script will hang trying to reach the DB.</p>

<h2>2. Register your PBX in EchoDesk</h2>
<ol>
  <li>Sign in as a tenant admin.</li>
  <li>Go to <strong>Settings → PBX → PBX Server</strong> (path: <code>/settings/pbx/server/</code>).</li>
  <li>Click <strong>Connect your PBX</strong> and fill in:
    <ul>
      <li><strong>Name</strong> — any friendly label (e.g. "Main PBX").</li>
      <li><strong>FQDN</strong> — the domain name of your Asterisk (e.g. <code>pbx.mycompany.com</code>).</li>
      <li><strong>Public IP</strong> — same address you emailed support.</li>
      <li><strong>AMI port</strong> — leave as <code>5038</code> unless you've changed it.</li>
    </ul>
  </li>
  <li>Click <strong>Save</strong>.</li>
</ol>
<p>Behind the scenes EchoDesk creates an isolated Postgres DB for you, provisions a dedicated RW role, runs the realtime schema migration, and shows you a one-line install command.</p>

<h2>3. Run the install script on your Asterisk</h2>
<p>SSH into your Asterisk server as root and paste the command the UI showed you. It looks like:</p>
<pre><code>curl -sSL https://api.echodesk.ge/api/pbx/install/&lt;token&gt;/ | sudo bash</code></pre>
<p>The token is already embedded when you use the <strong>Copy</strong> button in the UI. The script takes 30 – 60 seconds and will:</p>
<ul>
  <li>Write <code>/etc/asterisk/res_pgsql.conf</code> with your DB credentials.</li>
  <li>Add realtime mappings to <code>sorcery.conf</code> and <code>extconfig.conf</code>.</li>
  <li>Preload <code>res_config_pgsql</code> in <code>modules.conf</code>.</li>
  <li>Set <code>PGSSLMODE=require</code> via a systemd drop-in.</li>
  <li>Install an AMI user at <code>/etc/asterisk/manager.d/echodesk.conf</code>.</li>
  <li>Restart Asterisk and ping back to EchoDesk with its version.</li>
</ul>
<p>Existing config files are backed up with a timestamp (<code>.bak.YYYYMMDD-HHMMSS</code>) so you can roll back at any time.</p>

<h2>4. Verify the connection</h2>
<p>In the EchoDesk UI, refresh <code>/settings/pbx/server/</code>. You should see a green <strong>Active</strong> badge and a fresh <strong>Last seen</strong> timestamp.</p>
<p>On your Asterisk server, confirm:</p>
<pre><code>asterisk -rx 'realtime show pgsql status'
# → Connected to asterisk_&lt;you&gt;@...d.db.ondigitalocean.com for N seconds

asterisk -rx 'pjsip show endpoints'
# (empty at this point — that's expected, no extensions yet)</code></pre>

<h2>5. Add your first extension</h2>
<ol>
  <li>Go to <strong>Settings → PBX → Extensions</strong>, pick a user, assign an extension number (e.g. <code>100</code>) + password.</li>
  <li>Within a few seconds, on your Asterisk server:
    <pre><code>asterisk -rx 'pjsip show endpoint 100'</code></pre>
    shows the endpoint with <code>(realtime)</code> next to its source.
  </li>
  <li>Configure a softphone with:
    <ul>
      <li><strong>SIP server</strong>: your FQDN</li>
      <li><strong>WebSocket URI</strong>: <code>wss://&lt;your-fqdn&gt;:8089/ws</code></li>
      <li><strong>Username</strong>: the extension number</li>
      <li><strong>Password</strong>: the password you set in the UI</li>
      <li><strong>Transport</strong>: WSS</li>
    </ul>
  </li>
</ol>

<h2>Troubleshooting</h2>
<h3>Install command returns "Invalid or expired enrollment token"</h3>
<p>Tokens expire 24 hours after they're minted. In the UI, click <strong>Regenerate install token</strong> and rerun the command.</p>

<h3>Status stays "Awaiting install" after running the script</h3>
<p>The final step of the script posts back to <code>api.echodesk.ge</code>. Outbound HTTPS on port 443 from your Asterisk is required. Rerun with verbose output:</p>
<pre><code>curl -v https://api.echodesk.ge/api/pbx/install/&lt;token&gt;/</code></pre>

<h3>"Not connected" in <code>realtime show pgsql status</code></h3>
<ol>
  <li>Your public IP must be on our database firewall. If your IP changed, email support.</li>
  <li>Outbound port <strong>25060/tcp</strong> must be open from your server.</li>
  <li>If the password drifted, click <strong>Regenerate install token</strong> in the UI and rerun the install script — it rewrites <code>res_pgsql.conf</code>.</li>
</ol>

<h3>Asterisk takes forever to start</h3>
<p>Almost always the realtime DB connection is hanging. Check the points above. The systemd unit has a 300 s startup timeout; after that it'll be killed and restarted. <code>journalctl -u asterisk</code> shows the real error.</p>

<h3>Softphones won't register over WebSocket</h3>
<p>Your TLS cert chain must be valid — browsers refuse self-signed. Verify with:</p>
<pre><code>openssl s_client -connect &lt;your-fqdn&gt;:8089</code></pre>

<h2>Rolling back</h2>
<p>If you need to disconnect from EchoDesk:</p>
<ol>
  <li>On your Asterisk server, restore the backup config files:
<pre><code>cd /etc/asterisk
for f in res_pgsql.conf sorcery.conf extconfig.conf modules.conf; do
  BAK=$(ls -t $f.bak.* 2&gt;/dev/null | head -1)
  [ -n "$BAK" ] &amp;&amp; cp "$BAK" $f
done
rm -f /etc/systemd/system/asterisk.service.d/echodesk.conf
systemctl daemon-reload
systemctl restart asterisk</code></pre>
  </li>
  <li>In the EchoDesk UI, delete the PBX Server entry.</li>
</ol>
<p>Your realtime DB stays around in case you want to reconnect later. Contact support to delete it permanently.</p>

<h2>What EchoDesk does NOT do</h2>
<ul>
  <li>We don't install or upgrade Asterisk on your server — that's your responsibility.</li>
  <li>We don't manage SIP provider credentials — you enter them in the <strong>Trunks</strong> tab.</li>
  <li>We don't back up call recordings stored on your server. For centralised recordings, mount S3/Spaces or configure a webhook target.</li>
  <li>We don't SSH into your server. The install script runs only when you invoke it, under your root.</li>
</ul>
"""


CONTENT_KA = """
<h2>სანამ დაიწყებთ</h2>
<p>დარწმუნდით, რომ გაქვთ:</p>
<ul>
  <li><strong>Asterisk 18+</strong> Linux სერვერზე.</li>
  <li>საჯარო <strong>FQDN</strong> (მაგ. <code>pbx.mycompany.com</code>) თქვენს Asterisk-ზე მიბმული.</li>
  <li>ვალიდური <strong>TLS სერტიფიკატი</strong> (Let's Encrypt საკმარისია).</li>
  <li><strong>გამავალი</strong> კავშირი პორტ <strong>25060/tcp</strong>-ზე (realtime DB-სთან).</li>
  <li><strong>შემომავალი</strong> კავშირი პორტ <strong>8089/tcp</strong>-ზე (WSS) და თქვენს SIP პორტზე.</li>
  <li>Root/sudo წვდომა Asterisk სერვერზე.</li>
</ul>

<h2>1. გამოგვიგზავნეთ საჯარო IP</h2>
<p>დაწერეთ <a href="mailto:support@echodesk.ge">support@echodesk.ge</a>-ზე თქვენი Asterisk-ის საჯარო IPv4 მისამართი — დავამატებთ ჩვენს DB firewall-ში.</p>

<h2>2. დაარეგისტრირეთ PBX EchoDesk-ში</h2>
<ol>
  <li>შედით ტენანტის ადმინად.</li>
  <li>გადადით <strong>პარამეტრები → PBX → PBX სერვერი</strong>-ზე.</li>
  <li>დააჭირეთ <strong>დააკავშირეთ PBX</strong>-ს და შეავსეთ სახელი, FQDN, საჯარო IP.</li>
  <li>შეინახეთ.</li>
</ol>

<h2>3. გაუშვით ინსტალაციის ბრძანება</h2>
<p>SSH-ით Asterisk სერვერზე root-ად:</p>
<pre><code>curl -sSL https://api.echodesk.ge/api/pbx/install/&lt;token&gt;/ | sudo bash</code></pre>
<p>ბრძანებას სჭირდება 30 – 60 წამი. ძველი კონფიგი გადანახულია (<code>.bak.*</code>).</p>

<h2>4. შემოწმება</h2>
<pre><code>asterisk -rx 'realtime show pgsql status'
# Connected to asterisk_&lt;you&gt;@...

asterisk -rx 'pjsip show endpoints'</code></pre>

<h2>5. პირველი ხაზის დამატება</h2>
<p><strong>პარამეტრები → PBX → ხაზები</strong> → აირჩიეთ მომხმარებელი → ნომერი + პაროლი. რამდენიმე წამში softphone შეძლებს რეგისტრაციას.</p>

<h2>პრობლემების მოგვარება</h2>
<ul>
  <li><strong>Invalid or expired enrollment token</strong>: ტოკენი 24 საათის შემდეგ იწურება — განაახლეთ UI-ში.</li>
  <li><strong>Not connected</strong>: შეამოწმეთ firewall და პორტი 25060/tcp.</li>
  <li><strong>Asterisk არ ეშვება</strong>: <code>journalctl -u asterisk</code> აჩვენებს რეალურ შეცდომას.</li>
</ul>

<p>სრული ინგლისურენოვანი გაიდი ხელმისაწვდომია ამავე სტატიის English ვერსიაში.</p>
"""


CONTENT_RU = """
<h2>Требования перед началом</h2>
<ul>
  <li><strong>Asterisk 18+</strong> на Linux-сервере.</li>
  <li>Публичный <strong>FQDN</strong>, указывающий на ваш Asterisk.</li>
  <li>Действительный <strong>TLS-сертификат</strong> (Let's Encrypt подойдёт).</li>
  <li><strong>Исходящий</strong> доступ на порт <strong>25060/tcp</strong>.</li>
  <li><strong>Входящий</strong> доступ на <strong>8089/tcp</strong> (WSS) и SIP-порт.</li>
  <li>Root-доступ к серверу Asterisk.</li>
</ul>

<h2>1. Пришлите нам публичный IP</h2>
<p>Напишите на <a href="mailto:support@echodesk.ge">support@echodesk.ge</a> публичный IPv4-адрес вашего Asterisk — мы добавим его в firewall базы данных.</p>

<h2>2. Зарегистрируйте PBX в EchoDesk</h2>
<p><strong>Настройки → PBX → PBX Сервер</strong> → <strong>Подключить PBX</strong>. Заполните имя, FQDN, публичный IP. Сохраните.</p>

<h2>3. Запустите скрипт установки</h2>
<pre><code>curl -sSL https://api.echodesk.ge/api/pbx/install/&lt;token&gt;/ | sudo bash</code></pre>
<p>Скрипт выполняется 30 – 60 секунд. Старые конфиги сохраняются в <code>.bak.*</code>.</p>

<h2>4. Проверка</h2>
<pre><code>asterisk -rx 'realtime show pgsql status'
asterisk -rx 'pjsip show endpoints'</code></pre>

<h2>5. Первое расширение</h2>
<p><strong>Настройки → PBX → Расширения</strong> → выберите пользователя → номер и пароль. Через несколько секунд softphone сможет зарегистрироваться.</p>

<h2>Диагностика</h2>
<ul>
  <li><strong>Invalid or expired enrollment token</strong>: срок токена 24 часа — обновите в UI.</li>
  <li><strong>Not connected</strong>: проверьте firewall и порт 25060/tcp.</li>
  <li><strong>Asterisk не стартует</strong>: смотрите <code>journalctl -u asterisk</code>.</li>
</ul>

<p>Подробный гайд доступен в английской версии этой статьи.</p>
"""


def upsert_article(apps, schema_editor):
    HelpCategory = apps.get_model("help_center", "HelpCategory")
    HelpArticle = apps.get_model("help_center", "HelpArticle")

    # pbx-setup category must exist (seeded separately).
    category = HelpCategory.objects.filter(slug=CATEGORY_SLUG).first()
    if category is None:
        # Create it lazily if missing — keeps this migration self-contained.
        category = HelpCategory.objects.create(
            slug=CATEGORY_SLUG,
            name={"en": "PBX / IP Calling", "ka": "PBX / IP ზარები", "ru": "PBX / IP-звонки"},
            description={
                "en": "Guides for connecting and managing your own Asterisk server.",
                "ka": "Asterisk სერვერის დაკავშირების და მართვის ინსტრუქციები.",
                "ru": "Руководства по подключению и управлению сервером Asterisk.",
            },
            icon="phone",
            position=20,
            show_on_public=True,
            show_in_dashboard=True,
            required_feature_key="ip_calling",
        )

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


def delete_article(apps, schema_editor):
    HelpArticle = apps.get_model("help_center", "HelpArticle")
    HelpArticle.objects.filter(slug=ARTICLE_SLUG).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("help_center", "0001_initial"),
    ]
    operations = [
        migrations.RunPython(upsert_article, delete_article),
    ]
