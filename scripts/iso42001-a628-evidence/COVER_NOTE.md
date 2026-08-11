# LCORE A.6.2.8 — Cover note (ISO/IEC 42001 Annex A.6.2.8)

**Product:** Lightspeed Core Stack (LCORE) + OGX  
**Control:** AI system recording of event logs  
**Tickets:** [LCORE-3474](https://redhat.atlassian.net/browse/LCORE-3474) (evidence), [LCORE-3108](https://redhat.atlassian.net/browse/LCORE-3108) (spec), epic [LCORE-2314](https://redhat.atlassian.net/browse/LCORE-2314)

## Purpose

Product-specific **in-system** evidence that LCORE records AI-related events while the
system is in use. Complements the AI Event Log Specification; does not replace it.

## Specification reference

- AI Event Log Specification (Google Doc from LCORE-3108):  
  https://docs.google.com/document/d/1OlfXMaOqC0fb0vbWM1R9vKXWfxvQlYAdWLYxeOcShqk/edit
- Jira story for this evidence package: https://redhat.atlassian.net/browse/LCORE-3474

## Environment under test (this capture)

| Item | Value |
|------|--------|
| Capture UTC | 2026-08-11T07:14:37Z (inference) / 2026-08-11T07:15:00Z (screenshots) |
| LCORE config | `lightspeed-stack.yaml` |
| OGX config | `run.yaml` (`telemetry.enabled: true`) |
| Response ID | `resp_9396e5f4-cb87-4564-b98a-a7e70689fc86` |
| Conversation ID | `e07d2cbf83fcfc746e18d0dba1a100e822f42ed2b1718ce8` |
| Model | `openai/gpt-4o-mini` |
| Test label | `A.6.2.8 evidence test` |
| Deployment label | `a628-audit-evidence` |

## Enabled pipelines (this run)

| Pipeline | Status | Evidence file |
|----------|--------|---------------|
| Application / access logs | Enabled (`access_log: true`) | `screenshots/01-app-access-logs.png` |
| Prometheus `/metrics` | Always on | `screenshots/02-prometheus-metrics.png` |
| Splunk HEC | Enabled (`splunk.enabled: true`) | `screenshots/03-splunk-events.png` |
| Sentry | Enabled (`SENTRY_DSN` set) | `screenshots/04-sentry-events.png` |
| OpenTelemetry | Enabled (`OTEL_SDK_DISABLED=false` + exporter) | `screenshots/05-otel-spans.png` |
| Transcripts | Enabled (`transcripts_enabled: true`) | `screenshots/06-transcript.png` |
| Platform/K8s audit | Not in scope for this LCORE app capture | — |

## What each screenshot shows

1. **App/access logs** — Timestamped `/v1/query` lifecycle INFO from `query.py` (`RAG as a tool…`, `Consuming tokens`, `Getting available quotas`, `Storing query results`, `Building final response`) plus access line `POST /v1/query` → `200 OK`.
2. **Prometheus** — `ls_llm_calls_total{endpoint="/v1/responses",...}` and related gauges after the request.
3. **Splunk** — HEC event `sourcetype=responses_completed` with `conversation_id`, `model`, `inference_time`, `total_llm_tokens`, `received_at`.
4. **Sentry** — Envelope intake records (including earlier exception envelopes from pre-secret OTEL misconfig and subsequent traffic).
5. **OTEL** — OTLP HTTP exports to the local collector (`/v1/traces`) for the instrumented process.
6. **Transcript** — On-disk JSON with `metadata.timestamp`, `conversation_id`, `user_id`, query/response text.

## Ownership note (from AI Event Log Spec)

LCORE **emits** events. Customers/operators **aggregate and retain** them (Cluster Logging,
corporate Splunk, Tempo/Jaeger, Sentry org, object storage for transcripts).

## How to reproduce

```bash
# From repo root
bash scripts/iso42001-a628-evidence/start_audit_stack.sh
bash scripts/iso42001-a628-evidence/collect_evidence.sh
# Artifacts: scripts/iso42001-a628-evidence/output/{raw,html,screenshots}
```

Requires `OPENAI_API_KEY` (or another configured provider), podman/docker for OGX, and
`OTEL_ANONYMIZATION_SECRET` (set by the start script for local evidence runs).
