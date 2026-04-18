"""One-line-install endpoints for a tenant's BYO Asterisk server.

Flow:

1. ``GET /api/pbx/install/<token>/`` — returns a self-contained bash
   script. The tenant runs:

       curl -sSL https://api.echodesk.ge/api/pbx/install/<token>/ | sudo bash

2. The script writes ``/etc/asterisk/res_pgsql.conf``, appends sorcery /
   extconfig stanzas, installs the AGI script, restarts Asterisk.

3. On success it ``POST``s to ``/api/pbx/install/<token>/ping`` which
   flips the PbxServer status to ``active`` and records the Asterisk
   version.

The token is a single bearer secret — do not log it. Token is rotated
when the admin clicks "Regenerate token" in the UI.
"""
from __future__ import annotations

import logging

from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

log = logging.getLogger(__name__)


def _find_pbx_by_token(token: str):
    """Walk every tenant schema looking for a PbxServer with this token.

    Cached for 10 minutes to avoid repeated O(N) scans on every AGI call.
    Returns ``(tenant_schema, pbx_id)`` or ``(None, None)``.
    """
    if not token:
        return None, None
    from django.core.cache import cache
    from tenant_schemas.utils import schema_context
    from tenants.models import Tenant

    cache_key = f"pbx_token_lookup:{token}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    for tenant in Tenant.objects.exclude(schema_name="public"):
        try:
            with schema_context(tenant.schema_name):
                from crm.models import PbxServer
                pbx = PbxServer.objects.filter(enrollment_token=token).first()
                if pbx is not None:
                    result = (tenant.schema_name, pbx.id)
                    cache.set(cache_key, result, 600)
                    return result
        except Exception:  # noqa: BLE001
            continue

    return None, None


@csrf_exempt
@require_http_methods(["GET"])
def install_script(request, token: str):
    """Return the bash installer for this tenant's PBX.

    Served as ``text/x-shellscript`` so ``curl | bash`` works naturally.
    """
    schema, pbx_id = _find_pbx_by_token(token)
    if not schema:
        return HttpResponse("# Invalid or expired enrollment token\nexit 1\n",
                            status=404, content_type="text/plain")

    from tenant_schemas.utils import schema_context
    with schema_context(schema):
        from crm.models import PbxServer
        pbx = PbxServer.objects.filter(id=pbx_id).first()
        if pbx is None or (
            pbx.enrollment_expires_at and pbx.enrollment_expires_at < timezone.now()
        ):
            return HttpResponse("# Token expired — regenerate in EchoDesk\nexit 1\n",
                                status=410, content_type="text/plain")

        # Build script body with the server's creds baked in. Passwords
        # touch the wire here — that's unavoidable for an install script;
        # the user runs this exactly once and the network is HTTPS.
        script = _render_script(pbx, request)

    return HttpResponse(script, content_type="text/x-shellscript; charset=utf-8")


@csrf_exempt
@require_http_methods(["POST"])
def install_ping(request, token: str):
    """Called from the install script at the end to mark the PbxServer active."""
    schema, pbx_id = _find_pbx_by_token(token)
    if not schema:
        return JsonResponse({"error": "invalid token"}, status=404)

    import json
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        payload = {}

    from tenant_schemas.utils import schema_context
    with schema_context(schema):
        from crm.models import PbxServer
        pbx = PbxServer.objects.filter(id=pbx_id).first()
        if pbx is None:
            return JsonResponse({"error": "not found"}, status=404)

        pbx.status = PbxServer.STATUS_ACTIVE
        pbx.last_seen_at = timezone.now()
        pbx.asterisk_version = str(payload.get("asterisk_version", ""))[:64]
        pbx.save(update_fields=["status", "last_seen_at", "asterisk_version", "updated_at"])

    log.info("PBX install ping ok: tenant=%s pbx=%s", schema, pbx_id)
    return JsonResponse({"ok": True, "status": "active"})


def _render_script(pbx, request) -> str:
    """Render the bash installer.

    Heredoc templating — no external template engine. Keep the script
    idempotent and fail-fast (``set -e``). Uses the same config blocks
    we hand-crafted on pbx2 in Phase 1.
    """
    api_base = request.build_absolute_uri("/").rstrip("/")
    ping_url = f"{api_base}/api/pbx/install/{pbx.enrollment_token}/ping/"

    # Shell-escape credentials that may contain special chars.
    import shlex
    db_pass_q = shlex.quote(pbx.realtime_db_password)
    ami_user_q = shlex.quote(pbx.ami_username or "echodesk")
    ami_pass_q = shlex.quote(pbx.ami_password or "")
    api_token_q = shlex.quote(pbx.enrollment_token)

    return f"""#!/bin/bash
# EchoDesk BYO Asterisk install script
# PbxServer: {pbx.name} ({pbx.fqdn})
# Generated: {timezone.now().isoformat()}
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "Please run with sudo" >&2
  exit 1
fi

echo "==> EchoDesk Asterisk realtime install on $(hostname)"

# --- 1. Sanity checks -----------------------------------------------------
if ! command -v asterisk >/dev/null 2>&1; then
  echo "ERROR: asterisk binary not found. Install Asterisk 18+ first." >&2
  exit 2
fi

AST_VER=$(asterisk -V | head -1)
echo "  detected: $AST_VER"

# --- 2. Dependencies ------------------------------------------------------
apt-get update -qq
apt-get install -y -qq postgresql-client curl

# --- 3. Backups -----------------------------------------------------------
TS=$(date +%Y%m%d-%H%M%S)
for f in res_pgsql.conf sorcery.conf extconfig.conf modules.conf; do
  if [ -f /etc/asterisk/$f ]; then
    cp /etc/asterisk/$f /etc/asterisk/$f.bak.$TS
  fi
done
echo "  backups → /etc/asterisk/*.bak.$TS"

# --- 4. res_pgsql.conf ----------------------------------------------------
cat > /etc/asterisk/res_pgsql.conf <<PGCONF
; Managed by EchoDesk — do not hand-edit.
[general]
dbhost={pbx.realtime_db_host}
dbport={pbx.realtime_db_port}
dbname={pbx.realtime_db_name}
dbuser={pbx.realtime_db_user}
dbpass={db_pass_q}
dbappname=echodesk-{pbx.id}
requirements=warn
PGCONF
chown asterisk:asterisk /etc/asterisk/res_pgsql.conf
chmod 640 /etc/asterisk/res_pgsql.conf

# --- 5. extconfig.conf: inject into the existing [settings] stanza --------
python3 - <<'PYEOF'
import re, pathlib
p = pathlib.Path("/etc/asterisk/extconfig.conf")
txt = p.read_text()
block = \"\"\"
; === EchoDesk realtime (managed) ===
ps_endpoints => pgsql,general,ps_endpoints
ps_auths => pgsql,general,ps_auths
ps_aors => pgsql,general,ps_aors
ps_identifies => pgsql,general,ps_identifies
ps_registrations => pgsql,general,ps_registrations
ps_contacts => pgsql,general,ps_contacts
queues => pgsql,general,queues
queue_members => pgsql,general,queue_members
\"\"\"
# Strip any prior EchoDesk block so reruns don't duplicate.
txt = re.sub(r"\\n; === EchoDesk realtime.*?(?=\\n\\[|\\Z)", "", txt, flags=re.DOTALL)
# Inject into the first [settings] section.
txt = re.sub(r"(\\[settings\\][^\\[]*?)(?=\\n\\[|\\Z)", lambda m: m.group(1).rstrip() + block, txt, count=1, flags=re.DOTALL)
p.write_text(txt)
PYEOF

# --- 6. sorcery.conf: append PJSIP realtime wizard blocks -----------------
python3 - <<'PYEOF'
import re, pathlib
p = pathlib.Path("/etc/asterisk/sorcery.conf")
txt = p.read_text()
# Strip any previous EchoDesk block.
txt = re.sub(r"\\n; === EchoDesk realtime.*\\Z", "", txt, flags=re.DOTALL)
txt += \"\"\"
; === EchoDesk realtime (managed) ===
[res_pjsip]
endpoint=realtime,ps_endpoints
endpoint=config,pjsip.conf,criteria=type=endpoint
auth=realtime,ps_auths
auth=config,pjsip.conf,criteria=type=auth
aor=realtime,ps_aors
aor=config,pjsip.conf,criteria=type=aor
system=config,pjsip.conf,criteria=type=system
global=config,pjsip.conf,criteria=type=global
transport=config,pjsip.conf,criteria=type=transport
domain_alias=config,pjsip.conf,criteria=type=domain_alias

[res_pjsip_endpoint_identifier_ip]
identify=realtime,ps_identifies
identify=config,pjsip.conf,criteria=type=identify

[res_pjsip_outbound_registration]
registration=config,pjsip.conf,criteria=type=registration
\"\"\"
p.write_text(txt)
PYEOF

# --- 7. modules.conf preload ---------------------------------------------
if ! grep -q "preload => res_config_pgsql.so" /etc/asterisk/modules.conf; then
  sed -i "/^\\[modules\\]/a preload => res_config_pgsql.so" /etc/asterisk/modules.conf
fi

# --- 8. systemd drop-ins for SSL + safety ---------------------------------
mkdir -p /etc/systemd/system/asterisk.service.d
cat > /etc/systemd/system/asterisk.service.d/echodesk.conf <<UNIT
[Service]
Environment="PGSSLMODE=require"
TimeoutStartSec=300
UNIT

# --- 9. AMI user ---------------------------------------------------------
mkdir -p /etc/asterisk/manager.d
cat > /etc/asterisk/manager.d/echodesk.conf <<AMICONF
[{ami_user_q}]
secret = {ami_pass_q}
permit = 0.0.0.0/0
read = all
write = system,call,command,originate,reporting
AMICONF
chown -R asterisk:asterisk /etc/asterisk/manager.d

# --- 10. Reload + verify -------------------------------------------------
systemctl daemon-reload
systemctl reset-failed asterisk
systemctl restart asterisk

# Wait up to 60s for realtime connection to come up.
for i in $(seq 1 30); do
  if asterisk -rx 'realtime show pgsql status' 2>/dev/null | grep -q 'Connected'; then
    break
  fi
  sleep 2
done

STATUS=$(asterisk -rx 'realtime show pgsql status' 2>&1 | head -1)
echo "  realtime: $STATUS"

# --- 11. Ping back -------------------------------------------------------
curl -fsS -X POST -H 'Content-Type: application/json' \\
  --data "{{\\"asterisk_version\\": \\"$AST_VER\\"}}" \\
  {shlex.quote(ping_url)} >/dev/null
echo "==> EchoDesk install complete."
"""
