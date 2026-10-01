# OpenTelemetry Tracing

LCORE can export request traces to an OTLP endpoint (collector or backend) using the standard OpenTelemetry Python SDK. Tracing is **optional** and **off by default**.

This guide covers how to enable tracing, inspect the effective configuration at runtime, and verify that spans reach your OTLP backend. For architecture, span design, and collector deployment options, see the [OpenTelemetry tracing design](../design/observability-opentelemetry/observability-opentelemetry-design.md).

## Prerequisites

- LCORE runs under **`opentelemetry-instrument`**. The official container image starts the process this way when `OTEL_SDK_DISABLED=false` (the image entrypoint defaults to disabled), so the SDK initializes from environment variables before application code loads and supported libraries (for example FastAPI) are auto-instrumented.
- Tracing stays **disabled until you set exporter `OTEL_*` variables** at deploy time. Without a coherent exporter configuration, LCORE starts and serves traffic normally; no spans are exported.
- You need a reachable **OTLP endpoint** (OpenTelemetry Collector, Jaeger, Grafana Tempo, vendor backend, or similar). Deploying and operating that endpoint is outside this guide.
- When tracing is enabled, set **`OTEL_ANONYMIZATION_SECRET`** so LCORE can anonymize `user.id` span attributes.

## How configuration works

OpenTelemetry is **not configured in LCORE YAML** (`lightspeed-stack.yaml`). There is no `opentelemetry` or `observability` tracing section in the configuration file.

All tracing settings come from standard **`OTEL_*` environment variables** set when the process starts. The SDK reads them at launch; changes require a process restart.

To confirm what the running instance is using, call **`GET /v1/config`**. The response includes an **`observability.otel`** object with the effective `OTEL_*` values scraped from the process environment (OTLP header values are shown as `key=[REDACTED]`; certificate and client-key values as `[REDACTED]`).

## Required environment variables

Set these at minimum to export traces:

| Variable | Description |
|----------|-------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP receiver URL (for example `http://otel-collector:4318` for HTTP or `http://otel-collector:4317` for gRPC). |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | Export protocol. Common values: `http/protobuf` (HTTP, port 4318) or `grpc` (gRPC, port 4317). Must match your collector or backend. |
| `OTEL_SERVICE_NAME` | Service name attached to exported traces (for example `lightspeed-core`). |
| `OTEL_ANONYMIZATION_SECRET` | Secret used to HMAC-anonymize `user.id` in span attributes. Required when the SDK is enabled. |

## Common optional environment variables

| Variable | Description |
|----------|-------------|
| `OTEL_SDK_DISABLED` | Global kill switch. Set to `true` to disable the SDK and stop export without removing other `OTEL_*` variables. For the official container image, leave unset/`true` to skip `opentelemetry-instrument`, or set to `false` to enable it. |
| `OTEL_EXPORTER_OTLP_HEADERS` | Comma-separated `key=value` headers for authenticated OTLP export (for example `Authorization=Bearer <token>`). **Treat as a secret**; shown redacted in `/v1/config`. |
| `OTEL_PROPAGATORS` | W3C trace context propagators. Default continues upstream traces via `traceparent`. Set to `none` for standalone LCORE traces that ignore inbound `traceparent`. |
| `OTEL_TRACES_SAMPLER` | Sampling strategy (for example `parentbased_traceidratio`, `always_on`, `always_off`). |
| `OTEL_TRACES_SAMPLER_ARG` | Argument for the chosen sampler (for example `0.1` for 10% sampling with `traceidratio`). |
| `OTEL_PYTHON_FASTAPI_EXCLUDED_URLS` | Comma-separated URL patterns to exclude from FastAPI auto-instrumentation (for example `/liveness,/readiness,/metrics`). Reduces noise from health and metrics traffic. |

For the full upstream reference, see the [OpenTelemetry SDK environment variables](https://opentelemetry.io/docs/specs/otel/configuration/sdk-environment-variables/) documentation.

## Deployment examples

### Docker Compose

Add the required variables to the `lightspeed-stack` service `environment` block (or an `env_file` referenced by the service):

```yaml
services:
  lightspeed-stack:
    image: lightspeed-stack:local
    ports:
      - "8080:8080"
    volumes:
      - ./lightspeed-stack.yaml:/app-root/lightspeed-stack.yaml:ro
    environment:
      # ... existing LCORE variables ...
      OTEL_SDK_DISABLED: "false"
      OTEL_EXPORTER_OTLP_ENDPOINT: "http://otel-collector:4318"
      OTEL_EXPORTER_OTLP_PROTOCOL: "http/protobuf"
      OTEL_SERVICE_NAME: "lightspeed-core"
      OTEL_ANONYMIZATION_SECRET: "${OTEL_ANONYMIZATION_SECRET}"
      # Optional:
      # OTEL_PROPAGATORS: "tracecontext,baggage"
      # OTEL_PYTHON_FASTAPI_EXCLUDED_URLS: "/liveness,/readiness,/metrics"
      # OTEL_EXPORTER_OTLP_HEADERS: "Authorization=Bearer ${OTEL_AUTH_TOKEN}"
```

Restart the service after changing `OTEL_*` values.

## Runtime inspection

`GET /v1/config` requires authentication and the `GET_CONFIG` authorization action in secured deployments. With credentials configured for your environment:

```bash
curl -s -H "Authorization: Bearer ${TOKEN}" \
  "http://localhost:8080/v1/config"
```

The `otel` object is one section inside the full `configuration` payload returned by `/v1/config`. Outline when tracing is enabled:

```json
{
  "configuration": {
    "name": "lightspeed-stack",
    "service": { "..." },
    "ogx": { "..." },
    "authentication": { "..." },
    "authorization": { "..." },
    "inference": { "..." },
    "observability": {
      "otel": {
        "OTEL_EXPORTER_OTLP_ENDPOINT": "http://otel-collector:4318",
        "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
        "OTEL_SERVICE_NAME": "lightspeed-core",
        "OTEL_PROPAGATORS": "tracecontext,baggage",
        "OTEL_EXPORTER_OTLP_HEADERS": "Authorization=[REDACTED]"
      }
    }
  }
}
```

## Span, attribute, and event structure

LCORE emits a LCORE-owned span tree from application instrumentation. External backends are not merged into the tree.

### Typical inference request shape

```
<endpoint>.handle_request          # root span (e.g. query.handle_request)
├─ quota.check                     # when quota limiters are configured
├─ shield.moderate                 # when shields run
├─ rag.retrieve                    # inline RAG, when used
├─ llm.inference                   # model invoke + post-process
└─ topic.summary                   # background topic summary, when scheduled
```

Common root span names include `query.handle_request`, `streaming_query.handle_request`, `responses.handle_request`, `rlsapi_v1.infer`, `a2a.dispatch`, and `feedback.submit`. Catalog/admin handlers use names such as `models.list`, `providers.get`, and `mcp_server.register`.

### Attributes

Common attributes on inference spans:

| Attribute | Meaning |
|-----------|---------|
| `user.id` | Anonymized user identity |
| `session.id` | Conversation / session id |
| `request.input` / `response.output` | Request and response text |
| `llm.model.id` / `llm.provider.id` | Model and provider |
| `llm.usage.input_tokens` / `llm.usage.output_tokens` | Token usage |
| `inference_time` | Inference duration (seconds) |
| `quota.check.passed` | Quota gate result |
| `shield.result` / `shield.reason` | Moderation decision |
| `rag.input` / `rag.sources.count` / `rag.sources` / `rag_chunks` | Inline RAG metadata |
| `tool.calls.count` / `tool.calls.names` / `tool_calls` / `tool_results` | Tool activity |

### Events

Milestone events attached to the active span:

| Event | Typical span |
|-------|--------------|
| `validation.completed` | Root request span |
| `shield.rejected` / `pii.detected` | Shield / RLS path |
| `llm.inference.started` / `llm.inference.completed` | `llm.inference` |
| `rag.retrieval.completed` | `rag.retrieve` |
| `tool.execution.completed` | `llm.inference` |
| `llm.response.completed` / `turn.persisted` | Root request span |
| `topic.summary.task.started` / `topic.summary.task.finished` | `topic.summary` |
| `feedback.submitted` | `feedback.submit` |
| `a2a.dispatch.start` / `a2a.dispatch.end` | `a2a.dispatch` |

## Verification

1. **Set `OTEL_*` variables** on the LCORE deployment (required exporter variables at minimum, `OTEL_SDK_DISABLED=false` for the container image, and `OTEL_ANONYMIZATION_SECRET`) and **start or restart** LCORE so the process picks them up under `opentelemetry-instrument`.
2. **Confirm configuration** — call `GET /v1/config` and verify `configuration.observability.otel` shows the expected endpoint, protocol, and service name. Confirm sensitive headers appear redacted when set (for example `Authorization=[REDACTED]`).
3. **Generate trace traffic** — send an authenticated API request that exercises request handling, for example `POST /v1/query` with a test query.
   Health endpoints (`/liveness`, `/readiness`) also produce automatic FastAPI spans unless excluded via `OTEL_PYTHON_FASTAPI_EXCLUDED_URLS`.
4. **Confirm export** — in your OTLP collector or trace backend UI, look for spans with `service.name` matching `OTEL_SERVICE_NAME` and a recent timestamp from the test request. Filter by HTTP route or trace ID if your backend supports it.

If steps 1–2 succeed but no spans appear in step 4, check network reachability to `OTEL_EXPORTER_OTLP_ENDPOINT`, protocol/port alignment, collector logs, and any authentication headers.

## Expected behavior and limits

- **Missing or invalid exporter configuration does not block startup.** LCORE starts normally; spans are simply not exported until a valid OTLP configuration is in place.
- **Tracing failures do not change HTTP responses.** Export errors are handled on the observability path and do not alter status codes or response bodies for API clients.
- **LCORE does not propagate trace context to external backends.** Inbound W3C `traceparent` continuation is configurable via `OTEL_PROPAGATORS`; outbound propagation to dependencies is not an operator setup step for this feature.
