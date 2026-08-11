#!/usr/bin/env bash
# Start local mock receivers + LCORE/OGX with all A.6.2.8 pipelines enabled.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

EVIDENCE_DIR="$ROOT/scripts/iso42001-a628-evidence/output"
RAW_DIR="$EVIDENCE_DIR/raw"
mkdir -p "$RAW_DIR" /tmp/data/transcripts /tmp/data/feedback
mkdir -p "$(dirname "$RAW_DIR/splunk-events.jsonl")"

# Ensure Splunk token file exists (required by FilePath validation)
TOKEN="$ROOT/scripts/iso42001-a628-evidence/secrets/splunk-hec-token"
[[ -f "$TOKEN" ]] || { echo "a628-local-hec-token" > "$TOKEN"; chmod 600 "$TOKEN"; }

echo "==> Starting mock receivers (Splunk :8090, OTLP :4318, Sentry :9090)"
pkill -f "mock_receivers.py" 2>/dev/null || true
uv run python "$ROOT/scripts/iso42001-a628-evidence/collectors/mock_receivers.py" \
  --output-dir "$RAW_DIR" \
  --ports "8090,4318,9090" \
  >"$EVIDENCE_DIR/mock-receivers.log" 2>&1 &
echo $! > "$EVIDENCE_DIR/mock-receivers.pid"
sleep 1
curl -sf "http://127.0.0.1:8090/health" >/dev/null
echo "    mock receivers OK"

# OTEL + Sentry for LCORE process
export OTEL_SDK_DISABLED=false
export OTEL_SERVICE_NAME=lightspeed-core
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_TRACES_SAMPLER=always_on
export OTEL_PYTHON_FASTAPI_EXCLUDED_URLS="/liveness,/readiness,/metrics"
export OTEL_ANONYMIZATION_SECRET="${OTEL_ANONYMIZATION_SECRET:-a628-local-otel-anonymization-secret-not-for-prod}"
# Local mock Sentry DSN (key@host:port/project)
export SENTRY_DSN="http://a628publickey@127.0.0.1:9090/1"
export SENTRY_ENVIRONMENT=a628-audit-evidence
export OGX_LOGGING="root=INFO,inference=INFO,server=INFO"

# Load API keys from .env if present (without printing secrets)
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

echo "==> Starting OGX / llama-stack container"
make start-llama-stack-container

echo "==> Starting LCORE (logs → /tmp/lcore-a628-app.log)"
# Stop any previous local LCORE on 8080
pkill -f "lightspeed_stack.py" 2>/dev/null || true
sleep 1
nohup env OTEL_SDK_DISABLED=false \
  OTEL_SERVICE_NAME="$OTEL_SERVICE_NAME" \
  OTEL_EXPORTER_OTLP_ENDPOINT="$OTEL_EXPORTER_OTLP_ENDPOINT" \
  OTEL_EXPORTER_OTLP_PROTOCOL="$OTEL_EXPORTER_OTLP_PROTOCOL" \
  OTEL_TRACES_SAMPLER="$OTEL_TRACES_SAMPLER" \
  OTEL_PYTHON_FASTAPI_EXCLUDED_URLS="$OTEL_PYTHON_FASTAPI_EXCLUDED_URLS" \
  OTEL_ANONYMIZATION_SECRET="$OTEL_ANONYMIZATION_SECRET" \
  SENTRY_DSN="$SENTRY_DSN" \
  SENTRY_ENVIRONMENT="$SENTRY_ENVIRONMENT" \
  bash -c 'make run-stack' \
  > /tmp/lcore-a628-app.log 2>&1 &
echo $! > "$EVIDENCE_DIR/lcore.pid"

echo "==> Waiting for LCORE /liveness"
for i in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:8080/liveness" >/dev/null 2>&1; then
    echo "    LCORE is up"
    exit 0
  fi
  sleep 2
done
echo "LCORE failed to become ready; last log lines:"
tail -n 80 /tmp/lcore-a628-app.log || true
exit 1
