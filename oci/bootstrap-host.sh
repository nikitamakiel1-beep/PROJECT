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
# In particular, the private worker is not allowed to float with its branch:
# the installer clones the branch for access validation, then fetches/checks out
# the exact audited worker commit and refuses to continue if HEAD differs.
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
    'BRANCH = "feature/conway-colonial-integration"',
    f'BRANCH = "feature/conway-colonial-integration"\nWORKER_COMMIT = "{worker_commit}"',
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
replace_once(
    '                workerUrl=WORKER_URL,\n                tokenAcknowledged=False,',
    '                workerUrl=WORKER_URL,\n                workerCommit=WORKER_COMMIT,\n                tokenAcknowledged=False,',
    "deployment receipt source commit",
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
echo "[bootstrap] retries preserve the wallet/state and intentionally rebootstrap existing state"
echo "[bootstrap] zero-cost local mode is independent of Conway Compute credit survival tiers"
echo "[bootstrap] SSH ingress is not created by the Terraform stack"
echo "[bootstrap] setup portal auto-disables, deletes its credential files, and prunes build cache after acknowledgement"
echo "[bootstrap] complete"
