#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

exec > >(tee -a /var/log/conway-replicatio-bootstrap.log) 2>&1

echo "[bootstrap] starting Conway Replicatio browser-only host setup"

: "${SETUP_CODE:?SETUP_CODE is required}"
BOOTSTRAP_REF="${BOOTSTRAP_REF:-conway-oci-stack}"
BOOTSTRAP_ROOT=/opt/conway-bootstrap
PUBLIC_SOURCE="https://raw.githubusercontent.com/nikitamakiel1-beep/PROJECT/${BOOTSTRAP_REF}/oci"
WORKER_COMMIT="2689083b93296523b81614b6768f6c5b5d95fa27"
CADDY_IMAGE="caddy:2.11.4-alpine"
OLLAMA_IMAGE="ollama/ollama:0.32.5"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl git jq openssl python3

# ARM builds can transiently use more memory than the runtime. Add a private
# 4 GiB swapfile once; the VM still uses its 12 GiB Always Free RAM normally.
if ! swapon --show=NAME --noheadings | grep -qx '/swapfile'; then
  if [[ ! -f /swapfile ]]; then
    fallocate -l 4G /swapfile
    chmod 0600 /swapfile
    mkswap /swapfile >/dev/null
  fi
  swapon /swapfile
fi
if ! grep -qE '^/swapfile\s' /etc/fstab; then
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
cat >/etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-$VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
apt-get update
apt-get install -y --no-install-recommends docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker

docker version >/dev/null
docker compose version >/dev/null

# Defense in depth: OCI admits only 80/443, and the host firewall separately
# drops any non-loopback attempt to worker/supervisor/Ollama internal ports.
cat >/usr/local/sbin/conway-private-ports <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
for bin in iptables ip6tables; do
  command -v "$bin" >/dev/null 2>&1 || continue
  if ! "$bin" -C INPUT ! -i lo -p tcp -m multiport --dports 8080,8081,11434 -j DROP >/dev/null 2>&1; then
    "$bin" -I INPUT 1 ! -i lo -p tcp -m multiport --dports 8080,8081,11434 -j DROP
  fi
done
EOF
chmod 0700 /usr/local/sbin/conway-private-ports

cat >/etc/systemd/system/conway-private-ports.service <<'EOF'
[Unit]
Description=Keep Conway Replicatio internal ports loopback-only
After=network-online.target docker.service
Wants=network-online.target
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/conway-private-ports
RemainAfterExit=true

[Install]
WantedBy=multi-user.target
EOF

PUBLIC_IP="$(curl -4fsS --max-time 10 https://api.ipify.org || true)"
if ! [[ "$PUBLIC_IP" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  PUBLIC_IP="$(curl -4fsS --max-time 10 https://checkip.amazonaws.com | tr -d '[:space:]' || true)"
fi
if ! [[ "$PUBLIC_IP" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  echo "[bootstrap] unable to determine public IPv4 address" >&2
  exit 1
fi

WORKER_HOST="${PUBLIC_IP//./-}.sslip.io"
WORKER_URL="https://${WORKER_HOST}"

install -d -m 0700 "$BOOTSTRAP_ROOT" /opt/conway-replicatio /var/lib/conway-caddy /var/lib/conway-caddy-config

curl -fsSL "${PUBLIC_SOURCE}/portal.py" -o "${BOOTSTRAP_ROOT}/portal.py"

# Normalize the generic portal with the exact immutable deployment contract.
# The private worker cannot float with its branch, and the installer itself
# performs an Oracle-side persistence test before autonomous activation.
python3 - "${BOOTSTRAP_ROOT}/portal.py" "${WORKER_COMMIT}" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
worker_commit = sys.argv[2]
text = path.read_text(encoding="utf-8")

def replace_once(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"portal normalization anchor {label} expected once, found {count}")
    text = text.replace(old, new, 1)

replace_once(
    'import shutil\nimport subprocess',
    'import shutil\nimport sqlite3\nimport subprocess',
    "sqlite import",
)
replace_once(
    'BRANCH = "feature/conway-colonial-integration"',
    f'BRANCH = "feature/conway-colonial-integration"\nWORKER_COMMIT = "{worker_commit}"\nPERSISTENCE_PROOF = INSTALL_ROOT / "data" / "persistence-proof.json"',
    "worker commit constant",
)
replace_once(
    '                ], env=clone_env, timeout=300)\n            finally:',
    '''                ], env=clone_env, timeout=300)
                run(["git", "fetch", "origin", WORKER_COMMIT, "--depth=1"], cwd=INSTALL_ROOT / "app", env=clone_env, timeout=300)
                run(["git", "checkout", "--detach", WORKER_COMMIT], cwd=INSTALL_ROOT / "app", env=clone_env, timeout=120)
                resolved_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=INSTALL_ROOT / "app", text=True).strip()
                if resolved_commit != WORKER_COMMIT:
                    raise RuntimeError(f"Worker source verification failed: expected {WORKER_COMMIT}, got {resolved_commit}")
            finally:''',
    "worker checkout verification",
)
replace_once(
    '                "REPLICATIO_LOCAL_MODEL=" + LOCAL_MODEL,',
    '                "REPLICATIO_LOCAL_MODEL=" + LOCAL_MODEL,\n                "REPLICATIO_SOURCE_COMMIT=" + WORKER_COMMIT,\n                "REPLICATIO_ZERO_COST_LOCAL=true",',
    "worker environment audit metadata",
)
replace_once(
    '      REPLICATIO_LOCAL_MODEL: "qwen3:4b"',
    '      REPLICATIO_LOCAL_MODEL: "qwen3:4b"\n      REPLICATIO_ZERO_COST_LOCAL: "true"',
    "compose zero-cost mode",
)
replace_once(
    '                "autoProvision": False,',
    '                "autoProvision": False,\n                "allowExisting": True,',
    "retry-safe rebootstrap",
)
replace_once(
    '            api("/api/v1/bootstrap", control_token, method="POST", payload=bootstrap, timeout=180)',
    '''            try:
                api("/api/v1/stop", control_token, method="POST", payload={}, timeout=60)
            except Exception:
                pass
            api("/api/v1/bootstrap", control_token, method="POST", payload=bootstrap, timeout=180)''',
    "stop before rebootstrap",
)

persistence_helpers = r'''

def persistence_snapshot(seed=False):
    state_dir = INSTALL_ROOT / "data" / ".automaton"
    db_path = state_dir / "state.db"
    wallet_path = state_dir / "wallet.json"
    if not db_path.is_file():
        raise RuntimeError("SQLite state.db is missing from Oracle persistent storage")
    if not wallet_path.is_file():
        raise RuntimeError("Agent Wallet file is missing from Oracle persistent storage")

    wallet_raw = wallet_path.read_bytes()
    wallet_hash = hashlib.sha256(wallet_raw).hexdigest()
    try:
        wallet_meta = json.loads(wallet_raw.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Agent Wallet file is not valid JSON: {exc}")
    chain_type = str(wallet_meta.get("chainType") or "evm")

    con = sqlite3.connect(str(db_path), timeout=30)
    try:
        integrity_row = con.execute("PRAGMA integrity_check").fetchone()
        integrity = str(integrity_row[0] if integrity_row else "missing")
        if integrity.lower() != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {integrity}")

        tables = {str(row[0]) for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        required = {"schema_version", "identity", "turns", "kv", "model_registry"}
        missing = sorted(required - tables)
        if missing:
            raise RuntimeError("SQLite is missing required tables: " + ", ".join(missing))

        schema_row = con.execute("SELECT MAX(version) FROM schema_version").fetchone()
        schema_version = int(schema_row[0] or 0) if schema_row else 0
        if schema_version <= 0:
            raise RuntimeError("SQLite schema version is invalid")

        if seed:
            marker = secrets.token_hex(32)
            con.execute(
                "INSERT INTO kv(key,value,updated_at) VALUES('replicatio.persistence_marker',?,datetime('now')) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')",
                (marker,),
            )
            con.commit()
        else:
            marker_row = con.execute("SELECT value FROM kv WHERE key='replicatio.persistence_marker'").fetchone()
            marker = str(marker_row[0]) if marker_row else ""
            if len(marker) < 32:
                raise RuntimeError("SQLite persistence marker is missing after worker restart")

        page_count = int(con.execute("PRAGMA page_count").fetchone()[0])
        table_count = int(con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0])
    finally:
        con.close()

    return {
        "integrity": integrity,
        "schemaVersion": schema_version,
        "tableCount": table_count,
        "pageCount": page_count,
        "marker": marker,
        "walletHash": wallet_hash,
        "chainType": chain_type,
        "dbPath": str(db_path),
        "walletPath": str(wallet_path),
        "checkedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def seed_persistence_proof():
    snapshot = persistence_snapshot(seed=True)
    atomic_json(PERSISTENCE_PROOF, {
        "schema": "conway-replicatio/persistence-proof/v1",
        "workerCommit": WORKER_COMMIT,
        **snapshot,
    })
    return snapshot


def verify_persistence_proof():
    if not PERSISTENCE_PROOF.is_file():
        raise RuntimeError("Oracle persistence proof was not created")
    expected = json.loads(PERSISTENCE_PROOF.read_text(encoding="utf-8"))
    actual = persistence_snapshot(seed=False)
    if expected.get("workerCommit") != WORKER_COMMIT:
        raise RuntimeError("Persistence proof worker commit does not match the audited worker")
    if expected.get("marker") != actual.get("marker"):
        raise RuntimeError("SQLite persistence marker changed across container restart")
    if expected.get("walletHash") != actual.get("walletHash"):
        raise RuntimeError("Agent Wallet changed across container restart")
    atomic_json(PERSISTENCE_PROOF, {
        **expected,
        "verified": True,
        "verifiedAt": actual["checkedAt"],
        "postRestartIntegrity": actual["integrity"],
        "postRestartSchemaVersion": actual["schemaVersion"],
        "postRestartTableCount": actual["tableCount"],
    })
    return actual
'''
replace_once('\n\ndef page_html():', persistence_helpers + '\n\ndef page_html():', "persistence helper insertion")

replace_once(
    '            update_status(stage="checkpoint", progress=90, message="Creating the mandatory pre-activation integrity checkpoint")',
    '''            update_status(stage="persistence_seed", progress=87, message="Writing a persistence marker to Oracle SQLite and fingerprinting the Agent Wallet")
            seed_persistence_proof()

            update_status(stage="persistence_restart", progress=88, message="Restarting the cloud worker to prove wallet and SQLite persistence")
            run(["docker", "compose", "-f", "compose.yml", "restart", "worker"], cwd=INSTALL_ROOT, timeout=300)
            wait_for_worker(control_token, seconds=300)

            update_status(stage="persistence_verify", progress=89, message="Verifying SQLite integrity and unchanged Agent Wallet after restart")
            persistence = verify_persistence_proof()

            update_status(stage="checkpoint", progress=90, message="Creating the mandatory pre-activation integrity checkpoint")''',
    "automatic persistence restart proof",
)
replace_once(
    '                message="Replicatio is running with local qwen3:4b inference, zero spending, zero children and Honey payouts disabled.",',
    '                message="Replicatio is running. Oracle SQLite integrity, wallet persistence and local qwen3:4b tool calling were verified automatically; spending, children and Honey payouts remain disabled.",',
    "completion receipt message",
)
replace_once(
    '                workerUrl=WORKER_URL,\n                tokenAcknowledged=False,',
    '                workerUrl=WORKER_URL,\n                workerCommit=WORKER_COMMIT,\n                persistenceVerified=True,\n                sqliteIntegrity=persistence["integrity"],\n                sqliteSchemaVersion=persistence["schemaVersion"],\n                tokenAcknowledged=False,',
    "deployment receipt persistence metadata",
)
replace_once(
    '                    "workerUrl": status.get("workerUrl") or WORKER_URL,',
    '                    "workerUrl": status.get("workerUrl") or WORKER_URL,\n                    "persistenceVerified": bool(status.get("persistenceVerified")),\n                    "sqliteIntegrity": status.get("sqliteIntegrity"),\n                    "sqliteSchemaVersion": status.get("sqliteSchemaVersion"),',
    "status persistence metadata",
)
replace_once('if len(bucket) >= 12:', 'if len(bucket) >= 1000:', "long-running polling bucket")
replace_once('setInterval(refresh,5000)', 'setInterval(refresh,15000)', "long-running polling interval")
replace_once('image: ollama/ollama:latest', 'image: ollama/ollama:0.32.5', "pinned Ollama image")
path.write_text(text, encoding="utf-8")
PY
chmod 0700 "${BOOTSTRAP_ROOT}/portal.py"

cat >"${BOOTSTRAP_ROOT}/runtime.env" <<EOF
SETUP_CODE=${SETUP_CODE}
WORKER_HOST=${WORKER_HOST}
WORKER_URL=${WORKER_URL}
BOOTSTRAP_REF=${BOOTSTRAP_REF}
WORKER_COMMIT=${WORKER_COMMIT}
EOF
chmod 0600 "${BOOTSTRAP_ROOT}/runtime.env"

cat >/etc/systemd/system/conway-browser-setup.service <<'EOF'
[Unit]
Description=Conway Replicatio browser-only setup portal
After=network-online.target docker.service conway-private-ports.service
Wants=network-online.target
Requires=docker.service conway-private-ports.service

[Service]
Type=simple
EnvironmentFile=/opt/conway-bootstrap/runtime.env
ExecStart=/usr/bin/python3 /opt/conway-bootstrap/portal.py
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=/opt/conway-bootstrap /opt/conway-replicatio /var/log

[Install]
WantedBy=multi-user.target
EOF

# Once the owner clicks the portal's seal/acknowledge button, stop and disable
# the setup service automatically. This leaves only the worker gateway behind
# HTTPS and removes setup credentials and Docker build cache from the host.
cat >/usr/local/sbin/conway-seal-setup-check <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
STATUS=/opt/conway-bootstrap/status.json
if [[ -s "$STATUS" ]] && jq -e '.sealed == true' "$STATUS" >/dev/null 2>&1; then
  systemctl disable --now conway-browser-setup.service || true
  rm -f /etc/conway-replicatio-bootstrap.env /opt/conway-bootstrap/runtime.env /opt/conway-bootstrap/portal.py || true
  docker builder prune -af >/dev/null 2>&1 || true
  docker image prune -f >/dev/null 2>&1 || true
  apt-get clean || true
  systemctl disable --now conway-browser-setup-seal.timer || true
fi
EOF
chmod 0700 /usr/local/sbin/conway-seal-setup-check

cat >/etc/systemd/system/conway-browser-setup-seal.service <<'EOF'
[Unit]
Description=Seal Conway browser setup portal after owner acknowledgement

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/conway-seal-setup-check
EOF

cat >/etc/systemd/system/conway-browser-setup-seal.timer <<'EOF'
[Unit]
Description=Check whether Conway browser setup has been sealed

[Timer]
OnBootSec=2min
OnUnitActiveSec=1min
AccuracySec=10s
Persistent=true

[Install]
WantedBy=timers.target
EOF

# On every later Oracle VM boot, independently re-check the same persisted
# wallet fingerprint, SQLite marker and database integrity. This never exposes
# the wallet contents; it writes only a local verification receipt.
cat >/usr/local/sbin/conway-persistence-boot-check <<'PY'
#!/usr/bin/env python3
import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

root = Path("/opt/conway-replicatio/data")
proof_file = root / "persistence-proof.json"
status_file = root / "boot-persistence-status.json"
db_file = root / ".automaton" / "state.db"
wallet_file = root / ".automaton" / "wallet.json"

if not proof_file.is_file():
    sys.exit(0)

for _ in range(24):
    if db_file.is_file() and wallet_file.is_file():
        break
    time.sleep(5)

result = {
    "schema": "conway-replicatio/boot-persistence-status/v1",
    "checkedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "verified": False,
}
try:
    proof = json.loads(proof_file.read_text(encoding="utf-8"))
    wallet_hash = hashlib.sha256(wallet_file.read_bytes()).hexdigest()
    con = sqlite3.connect(str(db_file), timeout=30)
    try:
        integrity = str(con.execute("PRAGMA integrity_check").fetchone()[0])
        marker_row = con.execute("SELECT value FROM kv WHERE key='replicatio.persistence_marker'").fetchone()
        marker = str(marker_row[0]) if marker_row else ""
        schema_row = con.execute("SELECT MAX(version) FROM schema_version").fetchone()
        schema_version = int(schema_row[0] or 0) if schema_row else 0
    finally:
        con.close()
    if integrity.lower() != "ok":
        raise RuntimeError(f"SQLite integrity_check failed: {integrity}")
    if wallet_hash != proof.get("walletHash"):
        raise RuntimeError("Agent Wallet fingerprint changed after Oracle VM boot")
    if marker != proof.get("marker"):
        raise RuntimeError("SQLite persistence marker changed after Oracle VM boot")
    result.update({
        "verified": True,
        "sqliteIntegrity": integrity,
        "sqliteSchemaVersion": schema_version,
        "workerCommit": proof.get("workerCommit"),
    })
except Exception as exc:
    result["error"] = str(exc)

tmp = status_file.with_suffix(".tmp")
tmp.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
tmp.replace(status_file)
if not result["verified"]:
    sys.exit(1)
PY
chmod 0700 /usr/local/sbin/conway-persistence-boot-check

cat >/etc/systemd/system/conway-persistence-boot-check.service <<'EOF'
[Unit]
Description=Verify Conway wallet and SQLite persistence after Oracle VM boot
After=docker.service network-online.target
Wants=network-online.target
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/conway-persistence-boot-check

[Install]
WantedBy=multi-user.target
EOF

cat >"${BOOTSTRAP_ROOT}/Caddyfile" <<EOF
${WORKER_HOST} {
    encode zstd gzip

    header {
        Strict-Transport-Security "max-age=31536000"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "no-referrer"
        Permissions-Policy "camera=(), microphone=(), geolocation=()"
    }

    handle /setup* {
        reverse_proxy 127.0.0.1:9000
    }

    handle {
        reverse_proxy 127.0.0.1:8080
    }
}
EOF
chmod 0600 "${BOOTSTRAP_ROOT}/Caddyfile"

systemctl daemon-reload
systemctl enable --now conway-private-ports.service
systemctl enable --now conway-browser-setup.service
systemctl enable --now conway-browser-setup-seal.timer
systemctl enable conway-persistence-boot-check.service

docker rm -f conway-replicatio-caddy >/dev/null 2>&1 || true
docker run -d \
  --name conway-replicatio-caddy \
  --restart unless-stopped \
  --network host \
  -v "${BOOTSTRAP_ROOT}/Caddyfile:/etc/caddy/Caddyfile:ro" \
  -v /var/lib/conway-caddy:/data \
  -v /var/lib/conway-caddy-config:/config \
  "${CADDY_IMAGE}" >/dev/null

echo "[bootstrap] browser setup URL: ${WORKER_URL}/setup/"
echo "[bootstrap] private worker source pinned to ${WORKER_COMMIT}"
echo "[bootstrap] internal ports are blocked at both OCI and host firewall layers"
echo "[bootstrap] Caddy ${CADDY_IMAGE} and Ollama ${OLLAMA_IMAGE} are version-pinned"
echo "[bootstrap] 4 GiB swap protects the one-time ARM build from transient memory pressure"
echo "[bootstrap] installer automatically proves SQLite + Agent Wallet persistence across a worker restart before activation"
echo "[bootstrap] future Oracle VM boots automatically re-check wallet fingerprint, SQLite marker and PRAGMA integrity_check"
echo "[bootstrap] retries preserve the wallet/state and intentionally rebootstrap existing state"
echo "[bootstrap] zero-cost local mode is independent of Conway Compute credit survival tiers"
echo "[bootstrap] SSH ingress is not created by the Terraform stack"
echo "[bootstrap] setup portal auto-disables, deletes its credential files, and prunes build cache after acknowledgement"
echo "[bootstrap] complete"
