# ISO/IEC 42001 A.6.2.8 evidence toolkit

Helpers to enable LCORE/OGX log pipelines and capture in-system screenshots for
[LCORE-3474](https://redhat.atlassian.net/browse/LCORE-3474).

## Layout

| Path | Purpose |
|------|---------|
| `COVER_NOTE.md` | Auditor-facing cover note + spec links |
| `start_audit_stack.sh` | Mock HEC/OTLP/Sentry + OGX + LCORE with pipelines on |
| `start_splunk.sh` | Local Splunk Enterprise (Web UI + HEC) for real Splunk screenshots |
| `docker-compose.splunk.yaml` | Splunk container definition |
| `collect_evidence.sh` | Labeled inference + artifact/screenshot capture |
| `collectors/mock_receivers.py` | Local Splunk HEC / OTLP / Sentry intake |
| `collectors/render_evidence_html.py` | HTML pages for Chrome screenshots |
| `secrets/splunk-hec-token` | HEC token file (must match Splunk `SPLUNK_HEC_TOKEN`) |
| `output/` | Raw JSONL/logs, HTML, PNG screenshots (generated) |

## Main config changes

- `lightspeed-stack.yaml` — `access_log`, transcripts, Splunk HEC → `https://127.0.0.1:8088`, `deployment_environment`
- `run.yaml` — `telemetry.enabled: true` (OGX)

OTEL and Sentry remain env-driven (`OTEL_*`, `SENTRY_DSN`); the start script sets them
for a local evidence run.

## Splunk UI (recommended for HEC screenshots)

```bash
# From repo root — first start can take a few minutes
bash scripts/iso42001-a628-evidence/start_splunk.sh

# Open http://localhost:8000  (admin / A628Evidence!)
# Restart LCORE so it loads Splunk HTTPS HEC from lightspeed-stack.yaml
# Send a test query, then in Splunk search:
#   index=lcore_a628_evidence sourcetype=responses_* OR sourcetype=infer_*
```

Stop Splunk: `podman compose -f scripts/iso42001-a628-evidence/docker-compose.splunk.yaml down`
(or `docker compose ...`).

Do **not** run the mock HEC on `:8090` at the same time if you want events only in Splunk;
LCORE is configured for Splunk on `:8088`.
