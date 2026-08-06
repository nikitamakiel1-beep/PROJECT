#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ROOT=${REPLICATIO_ROOT:-/opt/conway-replicatio}
TOKEN=${REPLICATIO_CONTROL_TOKEN:-}
STATE_FILE="$ROOT/watchdog-state.json"
LOG_FILE="$ROOT/watchdog.log"
COMPOSE="$ROOT/compose.yml"
NOW=$(date +%s)

log() {
  printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >>"$LOG_FILE"
  chmod 600 "$LOG_FILE"
  if [[ $(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0) -gt 1000000 ]]; then
    tail -n 2000 "$LOG_FILE" >"$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
  fi
}

[[ ${#TOKEN} -ge 32 ]] || { log "control token unavailable"; exit 0; }
[[ -f "$COMPOSE" ]] || exit 0

if ! curl -fsS --max-time 8 http://127.0.0.1:8080/health >/tmp/replicatio-health.json 2>/dev/null; then
  log "gateway unavailable; asking Docker Compose to restore worker"
  docker compose -f "$COMPOSE" up -d worker >>"$LOG_FILE" 2>&1 || true
  exit 0
fi

CONFIGURED=$(jq -r '.configured // false' /tmp/replicatio-health.json)
RUNNING=$(jq -r '.running // false' /tmp/replicatio-health.json)
LOCKDOWN=$(jq -r '.lockdown // false' /tmp/replicatio-health.json)
READY=$(jq -r '.readyForActivation // false' /tmp/replicatio-health.json)
rm -f /tmp/replicatio-health.json

[[ "$CONFIGURED" == "true" && "$READY" == "true" && "$LOCKDOWN" != "true" ]] || exit 0
[[ "$RUNNING" != "true" ]] || exit 0

if [[ -f "$STATE_FILE" ]]; then
  RECENT=$(jq --argjson cutoff "$((NOW-600))" '[.restarts[]? | select(. >= $cutoff)]' "$STATE_FILE" 2>/dev/null || echo '[]')
else
  RECENT='[]'
fi
COUNT=$(jq 'length' <<<"$RECENT")

if (( COUNT >= 5 )); then
  log "crash-loop threshold reached; entering emergency lockdown"
  curl -fsS --max-time 20 -X POST http://127.0.0.1:8080/api/v1/emergency/lockdown \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    --data '{"reason":"Automatic watchdog lockdown after five restarts in ten minutes"}' \
    >/dev/null 2>&1 || true
  exit 0
fi

UPDATED=$(jq --argjson now "$NOW" '. + [$now]' <<<"$RECENT")
printf '{"restarts":%s,"updatedAt":"%s"}\n' "$UPDATED" "$(date -u +%FT%TZ)" >"$STATE_FILE"
chmod 600 "$STATE_FILE"

log "Automaton child is stopped; requesting bounded restart $((COUNT+1))/5"
RESPONSE=$(curl -fsS --max-time 30 -X POST http://127.0.0.1:8080/api/v1/start \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H "Idempotency-Key: watchdog-$NOW" \
  --data '{}' 2>&1 || true)
if grep -q '"ok":true' <<<"$RESPONSE"; then
  log "restart accepted"
else
  log "restart failed: $(sed -E 's/[A-Fa-f0-9]{64,}/[REDACTED]/g' <<<"$RESPONSE" | head -c 500)"
fi
