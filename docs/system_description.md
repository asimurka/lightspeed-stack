# Lightspeed Core Stack — System Description

| Field | Value |
|-------|-------|
| **System** | Lightspeed Core Stack (LCORE) |
| **Type** | AI orchestration middleware (inference, RAG, tool calling); does not train models |
| **Version** | Semantic versioning per product release |
| **Last updated** | June 2026 |

---

## 1. Purpose and Scope

LCORE is enterprise middleware between client applications and LLM backends. Built on [Llama Stack](https://llama-stack.readthedocs.io/), it orchestrates inference, injects RAG context, applies safety shields, enforces auth and quotas, and persists conversation state. It exposes REST APIs including OpenAI-compatible Responses endpoints.

**Intended use:** product Q&A, troubleshooting assistance, multi-turn conversations, agentic workflows (MCP tools, RAG), and A2A agent integration — all request-driven, with no unsupervised autonomous operation.

**Deployment:** stateful FastAPI service; library mode (embedded Llama Stack) or server mode (separate Llama Stack process). Configuration, models, RAG corpora, and MCP tools vary per deployment.

**In scope:** LCORE process, configuration, databases, optional transcript storage, API endpoints, prompt orchestration.

**Out of scope:**

| Component | Notes |
|-----------|-------|
| Downstream product UIs | Separate systems; user notices and acceptance workflows |
| LLM training / weights | Third-party inference APIs only |
| Llama Stack internals | Separate component |
| MCP server implementations | External HTTP services selected by deployer |
| RAG indexing pipeline | Pre-built corpora (e.g. via the rag-content tooling) |
| Identity provider | LCORE validates and forwards tokens |

---

## 2. What the System Does

| Capability | Description |
|------------|-------------|
| LLM inference | Non-streaming and SSE streaming via Llama Stack (OpenAI, Azure, Vertex AI, WatsonX, Bedrock, vLLM, etc.) |
| RAG | Inline context injection and tool-based `file_search`; BYOK (FAISS, pgvector) and OKP |
| MCP tool calling | HTTP MCP servers; static, K8s, client, OAuth, and header-propagation auth |
| Safety shields | Input/output content filtering via Llama Stack |
| Conversations | History, caching, optional topic summaries |
| Auth & RBAC | K8s, JWT/JWK, API key, RH Identity; 30+ actions |
| Quotas | Per-user and cluster token limits (HTTP 429 when exhausted) |
| Observability | Prometheus `/metrics`, structured logs, health/readiness |
| A2A / OpenResponses | Agent protocol and `POST /v1/responses` API |
| Data collection (optional) | Transcripts and feedback to JSON files; optional Dataverse export |

**Request pipeline:** validate → authenticate → authorize → quota check → load conversation → input moderation (raw user content only) → assemble context (system prompt, RAG, history, tools) → LLM call → output moderation → record usage/cache/metrics → respond.

---

## 3. What the System Does Not Do

| Exclusion | Detail |
|-----------|--------|
| Model training / fine-tuning | Consumes inference APIs only |
| Factual accuracy guarantee | Third-party LLM output is not verified |
| Autonomous operation | Client-initiated requests only (except quota-reset scheduler) |
| Human-in-the-loop for tools | Not yet supported (planned) |
| Agent Skills | Planned; script execution not supported |
| All Llama Stack providers | Only a tested subset is officially supported |
| Local/stdio MCP | HTTP/HTTPS only |
| OpenTelemetry | Metrics and logs only |
| Token issuance | Validates and forwards client credentials |
| End-user UI | API middleware for integrating products |
| Complete PII redaction | `redacted_query` in transcripts; deployer configures scrubbing |
| OpenResponses `reasoning` | Accepted then cleared (not implemented) |

---

## 4. Input Data

**Sources:** client HTTP requests, auth headers, MCP-HEADERS, `lightspeed-stack.yaml` / `run.yaml`, conversation history (User/Cache DB), RAG retrieval, MCP tool results.

**Key request fields** (`/v1/query`, `/v1/streaming_query`): `query`, `conversation_id`, `provider`, `model`, `system_prompt`, `attachments`, `no_tools`, `vector_store_ids`, `shield_ids`, `solr`, `generate_topic_summary`, `media_type`. `/v1/responses` uses the OpenResponses schema plus LCORE-specific extensions (`generate_topic_summary`, `shield_ids`, `solr`).

**Validation before LLM call:** schema (422), RBAC including model/shield overrides, attachment types, conversation ownership, quota (429), context window (413), MCP credential resolution (unresolved servers skipped), input shields (may block/redact).

**Not processed at query time:** RAG indexing (corpus must be pre-built); attachments passed as structured text, not OCR'd.

---

## 5. Output Data

**Response content:** LLM text (JSON or SSE), OpenResponses structured items, RAG references, conversation ID, token usage, remaining quota, optional topic summary, shield refusals.

**Persisted outputs:**

| Output | Destination |
|--------|-------------|
| Transcripts | Cache DB; optional JSON files |
| Conversation metadata | User DB |
| Token usage | Quota DB |
| Metrics | Prometheus |
| Feedback | Optional JSON files |

**Post-processing:** output shields, SSE event streams, HTTP error mapping (401, 403, 404, 413, 422, 429, 500, 503).

**Limitations:** output format depends on model; tool/RAG results are forwarded not validated; streaming may leave partial state.

---

## 6. Data Storage and Third Parties

**Databases:**

| DB | Contents | Retention |
|----|----------|-----------|
| User | Conversation metadata | Until explicit delete |
| Cache | Full transcripts | Medium-term; purgeable |
| Quota | Limits and usage | Reset on schedule |
| A2A | Agent context mappings | Session-oriented |

Transcript and feedback collection is **off by default**. When enabled, user IDs are hashed, queries stored as `redacted_query`, and files written to configurable local directories; an optional sidecar may export data to Red Hat Dataverse. Auth tokens are not persisted. Failed LLM calls do not consume quota.

**External dependencies:**

```
Client → LCORE → Llama Stack → LLM providers, vector stores, shields
              → MCP servers, SQL databases, optional Dataverse exporter
```

LCORE behaviour depends on LLM provider, Llama Stack version (currently enforced range 0.2.17–0.6.0 at startup), RAG corpus quality, MCP servers, and shield configuration. Deployers must assess third-party data processing (LLM providers, Llama Stack, MCP, vector stores) for their deployment.

---

## 7. Known Limitations

**Technical:** Llama Stack version gate at startup; variable tool-calling support by model; MCP must be HTTP and reachable at startup; MCP only in `lightspeed-stack.yaml` not `run.yaml`; partial OpenResponses support; no distributed tracing; OKP Solr range filters unsupported; BYOK PDF heading extraction issues; RAG untested for some provider configs.

**Operational:** fails to start without Llama Stack unless `allow_degraded_mode: true` (LLM unavailable); in-memory cache not shared across workers; quota is token-based not request-rate-based.

**Model/content:** hallucination risk; RAG coverage and retrieval quality bounds; context window limits; tool failures propagate to model; shield false positives/negatives.

**Auth:** K8s and RH Identity use broad default roles; JWK roles need JSONPath config.

---

## 8. Reasonably Foreseeable Misuse

| Scenario | LCORE mitigations | Deployer responsibility |
|----------|-------------------|-------------------------|
| Over-reliance on wrong answers | Shields, RAG, refusals | UI disclaimers; SME review |
| Prompt injection | Input shields on raw content | RAG curation; tool scoping |
| Conversation access breach | RBAC, ownership checks | IdP, network policy |
| MCP tool abuse | Auth, server skipping, `no_tools` | MCP permissions; product-level approval |
| Sensitive data in prompts | Optional transcript redaction | DPAs, data policies |
| No-auth in production | Dev/test only | `auth_enabled: true` |
| Unauthorized MCP registration | RBAC on `REGISTER_MCP_SERVER` | Restrict to admins |

Each production deployment needs its own impact assessment covering enabled MCP tools, RAG content, user population, and data flows.

---

## 9. Human Oversight

| Mechanism | Notes |
|-----------|-------|
| Client-initiated requests | No self-triggered inference |
| Shields | Block/refuse input or output |
| Tool restriction | `no_tools`, MCP skipping, registration RBAC |
| Quota halt | Blocks further inference |
| Process halt | Stop service, remove credentials, zero quota |
| Conversation review | Retrospective via Cache DB |
| Feedback | Optional `/feedback` endpoint |

**Gaps:** no per-tool-call approval gate yet; no automated output-quality evaluation.

**Halt options:** stop LCORE, revoke MCP/credentials, zero quota, block clients at gateway.

Downstream products must provide user-facing AI disclosure (AI-generated content, limitations, data use, tool invocation when enabled).

---

## 10. Monitoring and Traceability

Prometheus: API latency, LLM calls/failures, token usage, quota, shield violations. Logs and health/readiness endpoints for operations.

Per request (when caching enabled): user ID, conversation ID, provider/model, tokens, transcript, RAG references. No trace IDs across Llama Stack or MCP — correlate by timestamp and conversation ID.

Output quality is not scored in LCORE; product teams evaluate via feedback and testing.

---

## 11. Lifecycle

**Changes requiring review before production:** LCORE version upgrade, new model/provider, MCP or RAG changes, auth rule changes, enabling transcript export, shield changes.

**Retirement:** stop service → archive/delete databases and transcript dirs per policy → revoke provider and MCP credentials.

Releases follow semantic versioning with automated CI verification and container image builds.

---

## 12. Security Controls

Authentication (when enabled), RBAC, input/output shields, token quotas, secrets via files/env, MCP skip-on-auth-failure, configurable CORS, optional degraded mode (no LLM), cache/metrics audit trail, CI security checks.
