#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

exec > >(tee -a /var/log/conway-replicatio-bootstrap.log) 2>&1

echo "[bootstrap] starting Conway Replicatio browser-only host setup"

: "${SETUP_CODE:?SETUP_CODE is required}"
BOOTSTRAP_REF="${BOOTSTRAP_REF:-conway-oci-stack}"
BOOTSTRAP_ROOT=/opt/conway-bootstrap
PUBLIC_SOURCE="https://raw.githubusercontent.com/nikitamakiel1-beep/PROJECT/${BOOTSTRAP_REF}/oci"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl git jq openssl python3

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
chmod 0700 "${BOOTSTRAP_ROOT}/portal.py"

cat >"${BOOTSTRAP_ROOT}/runtime.env" <<EOF
SETUP_CODE=${SETUP_CODE}
WORKER_HOST=${WORKER_HOST}
WORKER_URL=${WORKER_URL}
BOOTSTRAP_REF=${BOOTSTRAP_REF}
EOF
chmod 0600 "${BOOTSTRAP_ROOT}/runtime.env"

cat >/etc/systemd/system/conway-browser-setup.service <<'EOF'
[Unit]
Description=Conway Replicatio browser-only setup portal
After=network-online.target docker.service
Wants=network-online.target
Requires=docker.service

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
systemctl enable --now conway-browser-setup.service

docker rm -f conway-replicatio-caddy >/dev/null 2>&1 || true
docker run -d \
  --name conway-replicatio-caddy \
  --restart unless-stopped \
  --network host \
  -v "${BOOTSTRAP_ROOT}/Caddyfile:/etc/caddy/Caddyfile:ro" \
  -v /var/lib/conway-caddy:/data \
  -v /var/lib/conway-caddy-config:/config \
  caddy:2-alpine >/dev/null

echo "[bootstrap] browser setup URL: ${WORKER_URL}/setup/"
echo "[bootstrap] ports 8080, 8081 and 11434 are not exposed publicly"
echo "[bootstrap] SSH ingress is not created by the Terraform stack"
echo "[bootstrap] complete"
