# Connect your Asterisk to EchoDesk

This guide is for **EchoDesk customers** who want to manage their own
Asterisk PBX from the EchoDesk admin panel. Once connected, every
extension, queue, trunk and inbound route you create in the UI takes
effect on your server in seconds — no more SSH, no more file edits,
no more `asterisk -rx 'pjsip reload'`.

## What you'll need before you start

| Requirement | Why |
|---|---|
| **Asterisk 18 or newer** running on a Linux server you control | EchoDesk talks to Asterisk via the realtime driver (`res_config_pgsql`) which is standard in 18+. Earlier versions are unsupported. |
| **A public FQDN** (e.g. `pbx.mycompany.com`) pointing at your Asterisk | Needed for softphone WebSocket (`wss://FQDN:8089/ws`) and for providers to deliver DIDs. |
| **A valid TLS certificate** on that FQDN | Browsers refuse to WebSocket to self-signed certs. Let's Encrypt works. |
| **Outbound internet** from your Asterisk on port **25060/tcp** | For the realtime DB connection to our managed Postgres. |
| **Inbound internet** on **8089/tcp** (WSS) and your SIP port | So softphones and providers can reach you. |
| Access to **systemd**, `apt`, and `/etc/asterisk/` (i.e. root/sudo) | The install script writes config files and adds a systemd drop-in. |

You do **not** need to install a database on your server — we run
your realtime DB on our managed Postgres cluster and give you the
connection string.

## Step 1 — Tell us your public IP

We'll add your Asterisk's public IP to our database firewall so your
server can connect to the realtime DB. Email support@echodesk.ge with
your public IPv4 address **before** clicking Connect in the UI.

## Step 2 — Register your PBX in EchoDesk

1. Sign in as a tenant admin.
2. Go to **Settings → PBX → PBX Server** (`/settings/pbx/server/`).
3. Click **Connect your PBX** and fill in:
   - **Name** — any label (e.g. "Main PBX").
   - **FQDN** — the domain name of your Asterisk (e.g. `pbx.mycompany.com`).
   - **Public IP** — same IP you sent to support in Step 1.
   - **AMI port** — leave as `5038` unless you've changed it.
4. Click **Save**.

Behind the scenes EchoDesk creates your isolated Postgres DB, your
dedicated RW role, runs the realtime schema migration, and displays
a one-line install command.

## Step 3 — Run the install script on your Asterisk

SSH into your Asterisk server as root and paste the command the UI
showed you. It looks like:

```bash
curl -sSL https://api.echodesk.ge/api/pbx/install/<token>/ | sudo bash
```

Replace `<token>` with the token in the UI (it's already embedded in
the copy button). The script takes about 30–60 seconds and:

- Writes `/etc/asterisk/res_pgsql.conf` with your DB credentials.
- Adds realtime mappings to `sorcery.conf` and `extconfig.conf`.
- Preloads the `res_config_pgsql` module.
- Sets `PGSSLMODE=require` on the Asterisk systemd service.
- Installs an AMI user at `/etc/asterisk/manager.d/echodesk.conf`.
- Restarts Asterisk.
- Reports success back to EchoDesk.

Existing config files are backed up with a timestamp suffix so you can
roll back at any time.

## Step 4 — Verify everything came up

Back in the EchoDesk UI, refresh `/settings/pbx/server/`. You should
see a green **Active** badge and a fresh **Last seen** timestamp.

On your Asterisk server, confirm:

```bash
asterisk -rx 'realtime show pgsql status'
# → Connected to asterisk_<you>@...d.db.ondigitalocean.com for N seconds

asterisk -rx 'pjsip show endpoints'
# (empty at this point — that's expected)
```

If both checks pass, you're ready to add extensions.

## Step 5 — Add your first extension

1. `/settings/pbx/extensions/` → pick a user → assign extension number.
2. Within a couple of seconds, `asterisk -rx 'pjsip show endpoint 100'`
   on your server shows the endpoint with `(realtime)` next to its
   source.
3. Configure a softphone to register using:
   - **SIP server**: your FQDN
   - **WebSocket URI**: `wss://<your-fqdn>:8089/ws`
   - **Username**: the extension number (e.g. `100`)
   - **Password**: the password you set in the UI
   - **Transport**: WSS

## Common problems and fixes

**The install command returns `# Invalid or expired enrollment token`.**
Tokens are valid for 24 hours from the moment the UI shows them.
Click **Regenerate install token** and rerun the command.

**The status stays on "Awaiting install" even after running the script.**
The script's final step posts back to `api.echodesk.ge`. Outbound
HTTPS on port 443 from your Asterisk is required. Rerun with
verbose output to see the error:

```bash
curl -v https://api.echodesk.ge/api/pbx/install/<token>/
```

**`realtime show pgsql status` says "Not connected".** Three things
to check:

1. Our database firewall still has your IP. If your IP changed,
   email support.
2. Outbound port 25060/tcp is open from your server.
3. The password in `/etc/asterisk/res_pgsql.conf` matches what's in
   EchoDesk. If you suspect drift, click **Regenerate install token**
   and run the install script again — it'll rewrite the file.

**Asterisk takes forever to start after the install.**
This almost always means the realtime DB connection is hanging. Check
outbound port 25060 and our firewall as above. The systemd unit has
a 300 s startup timeout; if it's still trying to start after that,
systemd will kill and restart. Look at `journalctl -u asterisk` for
the real error.

**Softphones won't register over WebSocket.**
Your TLS cert chain must be valid — browsers refuse self-signed.
Verify with `openssl s_client -connect <your-fqdn>:8089`.

## Rolling back

If you need to disconnect from EchoDesk:

1. On your Asterisk server, restore the backup config files:
   ```bash
   cd /etc/asterisk
   for f in res_pgsql.conf sorcery.conf extconfig.conf modules.conf; do
     BAK=$(ls -t $f.bak.* | head -1)
     [ -n "$BAK" ] && cp "$BAK" $f
   done
   rm -f /etc/systemd/system/asterisk.service.d/echodesk.conf
   systemctl daemon-reload
   systemctl restart asterisk
   ```
2. In the EchoDesk UI, delete the PbxServer entry.

Your realtime DB stays around in case you want to reconnect later
(contact support to delete it permanently).

## What EchoDesk does NOT do

- We don't install or upgrade Asterisk on your server. That's your
  responsibility.
- We don't manage your SIP provider credentials — you enter them in
  the **Trunks** tab of the EchoDesk UI.
- We don't back up call recordings stored on your server. If you want
  recordings centralized, mount S3/Spaces or configure a webhook target.
- We don't SSH into your server. The install script runs only as you
  invoke it, with root permissions you control.
