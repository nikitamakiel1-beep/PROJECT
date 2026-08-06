#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

SEED_FILE=/etc/conway-bootstrap.seed
if [[ ! -s "$SEED_FILE" ]]; then
  echo "Missing $SEED_FILE" >&2
  exit 1
fi
# shellcheck disable=SC1090
source "$SEED_FILE"

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  ca-certificates curl git jq openssl python3 python3-venv sqlite3 gzip \
  iptables iptables-persistent logrotate

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
cat >/etc/apt/sources.list.d/docker.sources <<DOCKER_REPO
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
DOCKER_REPO
apt-get update -y
apt-get install -y --no-install-recommends \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker

# Oracle network security rules are authoritative, but Ubuntu must also accept HTTPS locally.
iptables -C INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -p tcp --dport 80 -j ACCEPT
iptables -C INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -p tcp --dport 443 -j ACCEPT
netfilter-persistent save >/dev/null 2>&1 || true

PUBLIC_IP=""
for _ in $(seq 1 30); do
  PUBLIC_IP=$(curl -fsS -H 'Authorization: Bearer Oracle' \
    http://169.254.169.254/opc/v2/vnics/ 2>/dev/null \
    | jq -r '[.[] | select(.publicIp != null and .publicIp != "")][0].publicIp // empty' 2>/dev/null || true)
  [[ "$PUBLIC_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] && break
  sleep 5
done
if [[ ! "$PUBLIC_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  PUBLIC_IP=$(curl -fsS --max-time 10 https://api.ipify.org)
fi
if [[ ! "$PUBLIC_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Could not determine public IPv4 address" >&2
  exit 1
fi
DOMAIN="${PUBLIC_IP}.sslip.io"

install -d -m 0700 /opt/conway-bootstrap /opt/conway-bootstrap/caddy-data /opt/conway-bootstrap/caddy-config
install -d -m 0700 /opt/conway-replicatio

for file in portal.py installer.py; do
  : > "/tmp/${file}.gz.b64"
  if [[ "$file" == "portal.py" ]]; then
    parts=(00 01 02)
  else
    parts=(00 01 02.0 02.1 02.2 02.3 03)
  fi
  for part in "${parts[@]}"; do
    url="${STACK_RAW_BASE}/bootstrap/${file}.gz.b64.part${part}"
    curl -fsSL "$url" -o "/tmp/${file}.part"
    cat "/tmp/${file}.part" >> "/tmp/${file}.gz.b64"
  done
  base64 -d "/tmp/${file}.gz.b64" > "/tmp/${file}.gz"
  gzip -dc "/tmp/${file}.gz" > "/opt/conway-bootstrap/${file}"
  chmod 0700 "/opt/conway-bootstrap/${file}"
  rm -f "/tmp/${file}.gz.b64" "/tmp/${file}.gz" "/tmp/${file}.part"
done
curl -fsSL "${STACK_RAW_BASE}/bootstrap/watchdog.sh" -o "/opt/conway-bootstrap/watchdog.sh"
chmod 0700 /opt/conway-bootstrap/watchdog.sh

cat >/etc/conway-bootstrap.env <<ENV
BOOTSTRAP_TOKEN=${BOOTSTRAP_TOKEN}
STACK_RAW_BASE=${STACK_RAW_BASE}
PUBLIC_IP=${PUBLIC_IP}
DOMAIN=${DOMAIN}
BOOTSTRAP_ROOT=/opt/conway-bootstrap
REPLICATIO_ROOT=/opt/conway-replicatio
ENV
chmod 0600 /etc/conway-bootstrap.env

cat >/etc/systemd/system/conway-bootstrap-portal.service <<'UNIT'
[Unit]
Description=Conway Replicatio protected browser bootstrap portal
After=network-online.target docker.service
Wants=network-online.target
Requires=docker.service

[Service]
Type=simple
EnvironmentFile=/etc/conway-bootstrap.env
ExecStart=/usr/bin/python3 /opt/conway-bootstrap/portal.py
Restart=on-failure
RestartSec=5
User=root
Group=root
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/conway-bootstrap /opt/conway-replicatio /run /etc/systemd/system /etc/conway-bootstrap.env
ProtectHome=true

[Install]
WantedBy=multi-user.target
UNIT

cat >/opt/conway-bootstrap/Caddyfile <<'CADDY'
{$DOMAIN} {
    encode zstd gzip

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "no-referrer"
        Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()"
    }

    handle /bootstrap* {
        reverse_proxy 127.0.0.1:9000
    }

    handle /api/bootstrap/* {
        reverse_proxy 127.0.0.1:9000
    }

    handle {
        reverse_proxy 127.0.0.1:8080
    }
}
CADDY
chmod 0600 /opt/conway-bootstrap/Caddyfile

systemctl daemon-reload
systemctl enable --now conway-bootstrap-portal.service

docker rm -f conway-replicatio-caddy >/dev/null 2>&1 || true
docker run -d \
  --name conway-replicatio-caddy \
  --restart unless-stopped \
  --network host \
  --cap-drop ALL \
  --cap-add NET_BIND_SERVICE \
  --security-opt no-new-privileges:true \
  -e DOMAIN="$DOMAIN" \
  -v /opt/conway-bootstrap/Caddyfile:/etc/caddy/Caddyfile:ro \
  -v /opt/conway-bootstrap/caddy-data:/data \
  -v /opt/conway-bootstrap/caddy-config:/config \
  caddy:2-alpine

cat >/var/log/conway-bootstrap-ready.txt <<READY
Browser bootstrap portal requested at:
https://${DOMAIN}/bootstrap/#token=${BOOTSTRAP_TOKEN}

This token is sensitive. Reveal it only through the OCI Resource Manager output.
READY
chmod 0600 /var/log/conway-bootstrap-ready.txt

# The Terraform output already contains the token. Remove the cloud-init seed copy.
shred -u "$SEED_FILE" 2>/dev/null || rm -f "$SEED_FILE"

echo "Conway Replicatio bootstrap host ready at https://${DOMAIN}/bootstrap/"
