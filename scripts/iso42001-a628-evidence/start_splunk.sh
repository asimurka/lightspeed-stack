#!/usr/bin/env bash
# Start local Splunk with HEC enabled for A.6.2.8 evidence screenshots.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$ROOT/scripts/iso42001-a628-evidence/docker-compose.splunk.yaml"
TOKEN_FILE="$ROOT/scripts/iso42001-a628-evidence/secrets/splunk-hec-token"
INDEX="${SPLUNK_INDEX:-lcore_a628_evidence}"

export SPLUNK_PASSWORD="${SPLUNK_PASSWORD:-A628Evidence!}"
export SPLUNK_HEC_TOKEN="${SPLUNK_HEC_TOKEN:-a628-local-hec-token}"

# Keep LCORE token file in sync with the container HEC token
mkdir -p "$(dirname "$TOKEN_FILE")"
printf '%s\n' "$SPLUNK_HEC_TOKEN" > "$TOKEN_FILE"
chmod 600 "$TOKEN_FILE"

RUNTIME=""
if command -v podman >/dev/null 2>&1; then
  RUNTIME=podman
elif command -v docker >/dev/null 2>&1; then
  RUNTIME=docker
else
  echo "ERROR: need podman or docker"; exit 1
fi

COMPOSER=("$RUNTIME" compose)
if ! "$RUNTIME" compose version >/dev/null 2>&1; then
  if command -v "${RUNTIME}-compose" >/dev/null 2>&1; then
    COMPOSER=("${RUNTIME}-compose")
  else
    echo "ERROR: ${RUNTIME} compose plugin not available"; exit 1
  fi
fi

echo "==> Starting Splunk (UI :8000, HEC :8088) — first boot can take 2–5 minutes"
"${COMPOSER[@]}" -f "$COMPOSE_FILE" up -d

echo "==> Waiting for Splunk Web / management API"
for i in $(seq 1 80); do
  if curl -sf -k -u "admin:${SPLUNK_PASSWORD}" \
    "https://127.0.0.1:8089/services/server/info?output_mode=json" >/dev/null 2>&1; then
    echo "    Splunk management API is up"
    break
  fi
  if [[ "$i" -eq 80 ]]; then
    echo "ERROR: Splunk did not become ready in time"
    "$RUNTIME" logs --tail 80 lcore-a628-splunk || true
    exit 1
  fi
  sleep 5
done

echo "==> Ensuring index '${INDEX}' exists"
# 201 created, 409 already exists — both OK
HTTP=$(curl -sk -o /tmp/a628-splunk-index.json -w "%{http_code}" \
  -u "admin:${SPLUNK_PASSWORD}" \
  "https://127.0.0.1:8089/services/data/indexes" \
  -d "name=${INDEX}" || true)
echo "    create index HTTP ${HTTP}"

echo "==> Verifying HEC (HTTPS — retries until ready)"
HEC_OK=0
for i in $(seq 1 30); do
  CODE=$(curl -sk --connect-timeout 3 -o /tmp/a628-hec-test.json -w "%{http_code}" \
    -H "Authorization: Splunk ${SPLUNK_HEC_TOKEN}" \
    "https://127.0.0.1:8088/services/collector" \
    -d "{\"event\":{\"msg\":\"a628 hec probe\",\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"},\"sourcetype\":\"a628_probe\",\"index\":\"${INDEX}\"}" \
    || true)
  if [[ "$CODE" == "200" ]]; then
    echo "    HEC probe HTTP ${CODE} — OK"
    HEC_OK=1
    break
  fi
  echo "    HEC probe HTTP ${CODE:-000} (attempt ${i}/30)"
  sleep 3
done
if [[ "$HEC_OK" -ne 1 ]]; then
  echo "ERROR: HEC did not accept events. Check: podman logs lcore-a628-splunk"
  exit 1
fi

cat <<EOF

Splunk is ready.

  Web UI:   http://localhost:8000
  User:     admin
  Password: ${SPLUNK_PASSWORD}
  HEC:      https://127.0.0.1:8088/services/collector
  Token:    ${SPLUNK_HEC_TOKEN}  (also in ${TOKEN_FILE})
  Index:    ${INDEX}

Point LCORE Splunk config at HTTPS HEC (already in lightspeed-stack.yaml), restart LCORE,
send a /v1/query, then in Splunk Web search:

  index=${INDEX} sourcetype=responses_* OR sourcetype=infer_* OR source=*lightspeed*

Stop:
  ${COMPOSER[*]} -f ${COMPOSE_FILE} down
EOF
