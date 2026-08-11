#!/usr/bin/env bash
# Collect ISO/IEC 42001 A.6.2.8 in-system evidence for LCORE log pipelines.
# Prerequisites: mock receivers running; LCORE on :8080; OGX/llama-stack on :8321.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EVIDENCE_DIR="${EVIDENCE_DIR:-$ROOT/scripts/iso42001-a628-evidence/output}"
RAW_DIR="$EVIDENCE_DIR/raw"
SHOT_DIR="$EVIDENCE_DIR/screenshots"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
LABEL="${EVIDENCE_LABEL:-A.6.2.8 evidence test}"

mkdir -p "$RAW_DIR" "$SHOT_DIR"

LCORE_URL="${LCORE_URL:-http://127.0.0.1:8080}"
MODEL="${EVIDENCE_MODEL:-openai/gpt-4o-mini}"

echo "==> Checking LCORE readiness at $LCORE_URL"
curl -sf "$LCORE_URL/liveness" >/dev/null
curl -sf "$LCORE_URL/readiness" | tee "$RAW_DIR/03-readiness.json" >/dev/null

echo "==> Sending labeled inference request via /v1/query: $LABEL"
QUERY_MODEL="${MODEL##*/}"
QUERY_PROVIDER="${MODEL%%/*}"
QUERY_PAYLOAD=$(cat <<EOF
{
  "query": "$LABEL — please reply with a one-sentence confirmation that the request was received.",
  "model": "$QUERY_MODEL",
  "provider": "$QUERY_PROVIDER"
}
EOF
)

HTTP_CODE=$(curl -s -o "$RAW_DIR/inference-response.json" -w "%{http_code}" \
  -H "Content-Type: application/json" \
  -H "User-Agent: LCORE-A628-Evidence/1.0" \
  -X POST "$LCORE_URL/v1/query" \
  -d "$QUERY_PAYLOAD" || true)
echo "$HTTP_CODE" | tee "$RAW_DIR/inference-http-code.txt" >/dev/null

if [[ "$HTTP_CODE" != "200" ]]; then
  echo "/v1/query returned $HTTP_CODE — trying /v1/responses"
  INFER_PAYLOAD=$(cat <<EOF
{
  "model": "$MODEL",
  "input": "$LABEL — please reply with a one-sentence confirmation that the request was received."
}
EOF
  )
  curl -s -o "$RAW_DIR/inference-response.json" -w "%{http_code}" \
    -H "Content-Type: application/json" \
    -H "User-Agent: LCORE-A628-Evidence/1.0" \
    -X POST "$LCORE_URL/v1/responses" \
    -d "$INFER_PAYLOAD" | tee "$RAW_DIR/inference-http-code.txt" >/dev/null
fi

# Allow async Splunk / OTEL / transcript flush
sleep 3

echo "==> Capturing Prometheus /metrics"
curl -sf "$LCORE_URL/metrics" | tee "$RAW_DIR/02-prometheus-metrics.txt" >/dev/null

echo "==> Capturing application access log excerpt (uvicorn)"
if [[ -f /tmp/lcore-a628-app.log ]]; then
  # Prefer focused excerpt around successful /v1/responses
  python3 - <<'PY' || tail -n 200 /tmp/lcore-a628-app.log > "$RAW_DIR/01-app-access-logs.txt"
from pathlib import Path
log = Path("/tmp/lcore-a628-app.log").read_text(errors="replace").splitlines()
idxs = [i for i, line in enumerate(log) if "POST /v1/responses" in line]
out = []
for i in idxs[-3:]:
    out.extend(log[max(0, i - 20) : i + 10])
Path("scripts/iso42001-a628-evidence/output/raw/01-app-access-logs.txt").write_text(
    "\n".join(dict.fromkeys(out)) + "\n"
)
PY
elif command -v podman >/dev/null 2>&1 && podman ps --format '{{.Names}}' | grep -q lightspeed; then
  podman logs --tail 200 lightspeed-stack 2>&1 | tee "$RAW_DIR/01-app-access-logs.txt" >/dev/null || true
elif command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -q lightspeed; then
  docker logs --tail 200 lightspeed-stack 2>&1 | tee "$RAW_DIR/01-app-access-logs.txt" >/dev/null || true
else
  echo "NOTE: paste/capture LCORE stdout after the inference request into 01-app-access-logs.txt" \
    | tee "$RAW_DIR/01-app-access-logs.txt" >/dev/null
fi

echo "==> Capturing transcripts"
if [[ -d /tmp/data/transcripts ]]; then
  find /tmp/data/transcripts -type f -name '*.json' -printf '%T@ %p\n' 2>/dev/null \
    | sort -nr | head -1 | awk '{print $2}' \
    | while read -r newest; do
        [[ -n "$newest" ]] && cp -f "$newest" "$RAW_DIR/06-transcript.json"
      done
fi
if [[ ! -f "$RAW_DIR/06-transcript.json" ]]; then
  echo '{"note":"no transcript file found — confirm transcripts_enabled and storage path"}' \
    > "$RAW_DIR/06-transcript.json"
fi

echo "==> Capturing Splunk / OTEL / Sentry receiver dumps"
for f in splunk-events.jsonl otel-spans.jsonl sentry-events.jsonl; do
  if [[ -f "$RAW_DIR/$f" ]]; then
    cp -f "$RAW_DIR/$f" "$RAW_DIR/copy-$f" 2>/dev/null || true
  fi
done
# Keep last Splunk/OTEL/Sentry lines as dedicated artifacts
[[ -f "$RAW_DIR/splunk-events.jsonl" ]] && tail -n 5 "$RAW_DIR/splunk-events.jsonl" > "$RAW_DIR/03-splunk-events.jsonl"
[[ -f "$RAW_DIR/otel-spans.jsonl" ]] && tail -n 5 "$RAW_DIR/otel-spans.jsonl" > "$RAW_DIR/05-otel-spans.jsonl"
[[ -f "$RAW_DIR/sentry-events.jsonl" ]] && tail -n 5 "$RAW_DIR/sentry-events.jsonl" > "$RAW_DIR/04-sentry-events.jsonl"

echo "==> Effective observability config"
curl -sf "$LCORE_URL/v1/config" | tee "$RAW_DIR/config-snapshot.json" >/dev/null || true

echo "==> Rendering HTML viewers + Chrome screenshots"
python3 "$ROOT/scripts/iso42001-a628-evidence/collectors/render_evidence_html.py" \
  --raw-dir "$RAW_DIR" \
  --html-dir "$EVIDENCE_DIR/html" \
  --timestamp "$TS" \
  --label "$LABEL"

CHROME="${CHROME_BIN:-google-chrome}"
if command -v "$CHROME" >/dev/null 2>&1; then
  for html in "$EVIDENCE_DIR"/html/*.html; do
    base="$(basename "$html" .html)"
    "$CHROME" --headless --disable-gpu --no-sandbox --window-size=1400,900 \
      --screenshot="$SHOT_DIR/${base}.png" "file://$html" >/dev/null 2>&1 || true
  done
else
  echo "Chrome not found; HTML evidence left in $EVIDENCE_DIR/html (open and screenshot manually)"
fi

echo "==> Evidence package ready under $EVIDENCE_DIR"
ls -la "$SHOT_DIR" "$RAW_DIR" | sed -n '1,80p'
