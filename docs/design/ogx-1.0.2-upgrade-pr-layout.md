# OGX 1.0.2 upgrade — PR layout

Plan for delivering the flattened `bump_lls_to_0.7` delta (three incremental bumps
`0.7.2` → `0.8.0` → `1.0.2`) as isolated stacked PRs on the feature branch, without
replaying intermediate per-version edits of the same files/lines.

**Source of truth for the final code:** tip of `bump_lls_to_0.7`  
**Base for the flattened diff:** parent of first bump commit (`c964f840^`)

## Goals

1. Bump libraries straight to **ogx 1.0.2** (no intermediate library pins).
2. Prefer **component + corresponding unit/integration tests** in the same PR.
3. Prefer PRs under ~1000 lines when practical; note unavoidable outliers.
4. Keep behavioral/API ownership per component PR; accept that PR3 (package rename) may
   touch the same files again later for non-trivial API changes (rename hunks only in PR3).

## Stacking notes

- Merge PRs into the feature branch in order.
- CI may still be red after PR1–PR3 until API adaptation PRs land (rename alone does not
  fix breaking API changes).
- Do not re-apply the intermediate 0.7.2 / 0.8.0 edit sequences; take the final tip state
  of each file from `bump_lls_to_0.7`.
- After PR3, later PRs should assume `ogx_*` imports/symbols already and only land
  behavioral diffs.

## Shared-file ownership (intentional minor overlaps)

| File | Split |
|------|--------|
| `src/constants.py` | PR1: `MAXIMAL_SUPPORTED_LLAMA_STACK_VERSION`; PR6: shield ID constants |
| `src/models/api/responses/successful/catalog.py` | PR4: `CatalogTool`; PR6: `CatalogShield` |
| `src/configuration.py` | PR3: `ogx` import rename; PR6: `shields` property only |
| `tests/e2e/configuration/*/lightspeed-stack.yaml` | PR6 only (LCS `shields:` blocks), **not** PR2 |
| Stack `run.yaml` family | PR2 only (OGX stack schema), including removal of stack-owned shields |

---

## PR1 — Bump dependencies to ogx 1.0.2

**Summary:** Pin `ogx` / `ogx-client` / `ogx-api` to 1.0.2 and raise the supported version ceiling.  
**Size:** ~360 lines

**Files:**

- `pyproject.toml`
- `uv.lock`
- `src/constants.py` — only `MAXIMAL_SUPPORTED_LLAMA_STACK_VERSION = "1.0.2"`

---

## PR2a — OGX 1.0 stack run configs (examples / runtime)

**Summary:** Migrate example and runtime Llama Stack / OGX `run.yaml` files to the 1.0-compatible provider/API schema.  
**Size:** ~860 lines

**Files:**

- `run.yaml`
- `src/data/default_run.yaml`
- `examples/run.yaml`
- `examples/azure-run.yaml`
- `examples/bedrock-run.yaml`
- `examples/vertexai-run.yaml`
- `examples/watsonx-run.yaml`
- `examples/vllm-rhaiis.yaml`
- `examples/vllm-rhelai.yaml`
- `examples/vllm-rhoai.yaml`
- `examples/profiles/inline-faiss.yaml`
- `examples/profiles/openai-remote.yaml`

---

## PR2b — OGX 1.0 stack run configs (tests / CI)

**Summary:** Same schema migration for test and CI stack configs.  
**Size:** ~890 lines

**Files:**

- `tests/configuration/run.yaml`
- `tests/configuration/minimal-stack.yaml`
- `tests/e2e/configs/run-azure.yaml`
- `tests/e2e/configs/run-bedrock.yaml`
- `tests/e2e/configs/run-ci.yaml`
- `tests/e2e/configs/run-rhaiis.yaml`
- `tests/e2e/configs/run-rhelai.yaml`
- `tests/e2e/configs/run-vertexai.yaml`
- `tests/e2e/configs/run-watsonx.yaml`
- `tests/e2e-prow/rhoai/configs/run.yaml`

---

## PR3 — Mechanical `llama_stack_*` → `ogx_*` rename (single PR)

**Summary:** One larger, mostly trivial PR that renames packages/imports/CLI/env across the
whole tree (`llama_stack_*` / `llama stack` / `LLAMA_STACK_*` → `ogx_*` / `ogx stack` /
`OGX_*`, including client type renames such as `AsyncLlamaStackClient` → `AsyncOgxClient`).
No intentional API behavior changes in this PR.  
**Size:** larger (~1.5k+ lines possible); acceptable because changes are mechanical and easy to review.

**Scope:**

- Apply the rename in **all** affected `src/`, `tests/`, `scripts/`, `Makefile`,
  docker-compose, and prow manifest files — including files that later component PRs will
  touch again for real API work.
- Leave out stack `run.yaml` schema migrations (PR2) and dependency pins (PR1).
- Leave out non-rename logic (tools/MCP rewrite, shields ownership, streaming cleanup, etc.).

**Typical rename surface:**

- Imports: `llama_stack_client` → `ogx_client`, `llama_stack_api` → `ogx_api`,
  `llama_stack.core` → `ogx.core`, etc.
- Symbols: `AsyncLlamaStackClient` → `AsyncOgxClient`, library client class names, etc.
- CLI: `llama stack run` / `uv run llama stack …` → `ogx stack …`
- Env: `LLAMA_STACK_LOGGING` → `OGX_LOGGING`
- Strings / comments / test patches that only mirror the package rename

**Files:** essentially every file in the flattened bump diff that contains the rename
(roughly 100+ files). Review as a mechanical sweep rather than a file-by-file ownership list.

**Follow-up rule for later PRs:** start from the post-PR3 tree; do not redo import renames —
only land behavioral/API hunks and matching tests.

---

## PR4 — Tools adaptation

**Summary:** Tools endpoint and MCP/builtin tool helpers for OGX 1.0, with tests.  
List tools via direct MCP discovery + builtin file-search catalog (no OGX toolgroups list).  
Keep skills capability merge in `tools.py`; `CatalogTool` typing for `get_agent_capability_tools` deferred to a follow-up.  
**Size:** ~1.7–2.0k lines (outlier: large `test_tools.py` rewrite)

**Files:**

- `src/app/endpoints/tools.py`
- `src/utils/mcp_tools.py` (new)
- `src/utils/builtin_tools.py` (new)
- `src/utils/tool_formatter.py`
- `src/models/common/tools.py` (new)
- `src/models/api/responses/successful/catalog.py` — `CatalogTool` typing only (not `CatalogShield`)
- `tests/unit/utils/test_mcp_tools.py`
- `tests/unit/utils/test_builtin_tools.py`
- `tests/unit/app/endpoints/test_tools.py`
- `tests/integration/endpoints/test_tools_integration.py`
- `tests/e2e/features/mcp.feature` — MCP reset step rename (tools scenarios)
- `tests/e2e/features/skills.feature` — file-search catalog expectations (tools listing)
- `tests/e2e/features/info.feature` — tools scenario unskip + file-search provider
- `tests/e2e/features/steps/common.py` — `MCP configuration is reset for a new scenario`
- `tests/e2e/utils/llama_stack_utils.py` — remove MCP toolgroup unregister helpers
- `tests/e2e/utils/utils.py` — library-mode storage reset docstring

---

## PR5 — MCP servers adaptation

**Summary:** MCP servers endpoint adaptations for OGX 1.0, with tests.  
Register/delete are LCS-config only (no OGX toolgroup calls).  
**Size:** ~450–500 lines

**Files:**

- `src/app/endpoints/mcp_servers.py`
- `tests/unit/app/endpoints/test_mcp_servers.py`
- `src/utils/common.py` — remove MCP toolgroup registration helpers
- `src/app/main.py` — drop startup `register_mcp_servers_async` call
- `tests/unit/utils/test_common.py` (deleted with helpers)
- `tests/e2e/features/llama_stack_disrupted.feature` — remove MCP register→503 scenario only
- `tests/integration/test_openapi_json.py` — drop 503 from mcp-servers post/delete expected codes
- `tests/e2e/features/mcp.feature` — MCP reset step rename
- `tests/e2e/features/steps/common.py` — `MCP configuration is reset for a new scenario`
- `tests/e2e/utils/llama_stack_utils.py` — remove MCP toolgroup unregister helpers
- `tests/e2e/utils/utils.py` — library-mode storage reset docstring
- any MCP-endpoint-only helpers still tied to this endpoint (if not already in PR4)

---

## PR6 — Shields owned by LCS

**Summary:** Move shield configuration and listing from stack Safety API into LCS-owned config/capabilities.  
**Size:** ~900–1100 lines

**Files:**

- `src/models/config.py` — `ShieldConfiguration` + `Configuration.shields`
- `src/configuration.py` — `shields` property only (import rename already in PR3)
- `src/constants.py` — shield ID constants only
- `src/models/common/shields.py` (new)
- `src/utils/shields.py`
- `src/app/endpoints/shields.py`
- `src/pydantic_ai_lightspeed/capabilities/question_validity/_capability.py`
- `src/pydantic_ai_lightspeed/capabilities/question_validity/core.py` (new)
- `src/telemetry/configuration_snapshot.py`
- `src/models/api/responses/successful/catalog.py` — `CatalogShield` typing / examples
- `tests/e2e/configuration/library-mode/lightspeed-stack.yaml` — `shields:` block
- `tests/e2e/configuration/server-mode/lightspeed-stack.yaml` — `shields:` block
- `tests/unit/utils/test_shields.py`
- `tests/unit/app/endpoints/test_shields.py`
- `tests/unit/test_configuration.py` / dump-config tests for shields
- `tests/unit/pydantic_ai_lightspeed/capabilities/question_validity/test_capability.py`
- `tests/unit/telemetry/conftest.py` / `test_configuration_snapshot.py` as needed for shields

---

## PR7 — Streaming query cleanup

**Summary:** Remove deprecated query/streaming helpers (`retrieve_response`, `retrieve_response_generator`, `generate_response`, `response_generator`) and their unit tests; keep current handler/shields behavior.  
**Size:** ~3k lines (outlier because of `test_streaming_query.py`)

**Files:**

- `src/app/endpoints/query.py`
- `src/app/endpoints/streaming_query.py`
- `src/utils/agents/query.py` (docstring only, if it still references deleted helper)
- `tests/unit/app/endpoints/test_query.py`
- `tests/unit/app/endpoints/test_streaming_query.py`
- related thin streaming integration test updates if they are more than rename-only:
  - `tests/integration/endpoints/test_streaming_query_integration.py`
  - `tests/integration/endpoints/test_streaming_query_byok_integration.py`

---

## PR8 — Query endpoint adaptation

**Summary:** Query endpoint and helpers for OGX 1.0, with tests.  
**Size:** ~550–650 lines

**Files:**

- `src/app/endpoints/query.py`
- `src/utils/query.py`
- `src/utils/agents/query.py`
- `src/utils/vector_search.py` (if primarily driven by query path)
- `tests/unit/app/endpoints/test_query.py`
- `tests/unit/utils/test_query.py`
- `tests/unit/utils/agents/test_query.py`
- `tests/integration/endpoints/test_query_integration.py`
- `tests/integration/endpoints/test_query_byok_integration.py`

---

## PR9 — Responses endpoint adaptation

**Summary:** Responses endpoint / telemetry / helpers for OGX 1.0, with tests.  
**Size:** ~900–1000 lines

**Files:**

- `src/app/endpoints/responses.py`
- `src/app/endpoints/responses_telemetry.py`
- `src/utils/responses.py`
- response model / context tweaks used only here (if still remaining)
- `tests/unit/app/endpoints/test_responses.py`
- `tests/unit/app/endpoints/test_responses_splunk.py`
- `tests/unit/utils/test_responses.py`
- `tests/integration/endpoints/test_responses_integration.py`
- `tests/integration/endpoints/test_responses_byok_integration.py`

---

## PR10 — rlsapi v1 endpoint adaptation

**Summary:** rlsapi v1 endpoint adaptations for OGX 1.0, with tests.  
**Size:** ~350–400 lines

**Files:**

- `src/app/endpoints/rlsapi_v1.py`
- `tests/unit/app/endpoints/test_rlsapi_v1.py`
- `tests/integration/endpoints/test_rlsapi_v1_integration.py`

---

## PR11 — Client + Pydantic AI / OGX provider

**Summary:** Async client and Pydantic AI Llama Stack / OGX provider/transport adaptations, with tests.  
**Size:** ~700–900 lines

**Files:**

- `src/client.py`
- `src/pydantic_ai_lightspeed/llamastack/__init__.py`
- `src/pydantic_ai_lightspeed/llamastack/_model.py`
- `src/pydantic_ai_lightspeed/llamastack/_provider.py`
- `src/pydantic_ai_lightspeed/llamastack/_transport.py`
- `src/utils/pydantic_ai_helpers.py`
- `src/utils/agents/streaming.py` (if not already claimed by query/streaming PRs)
- `tests/unit/test_client.py`
- `tests/unit/pydantic_ai_lightspeed/llamastack/test_model.py`
- `tests/unit/pydantic_ai_lightspeed/llamastack/test_provider.py`
- `tests/unit/pydantic_ai_lightspeed/llamastack/test_transport.py`
- `tests/unit/utils/test_pydantic_ai.py`
- `tests/unit/utils/agents/test_streaming.py` (if paired with agents streaming changes here)

---

## PR12a — Conversations v1 adaptation

**Summary:** Conversations v1 endpoint / utils for OGX 1.0, with tests.  
**Size:** ~200–300 lines

**Files:**

- `src/app/endpoints/conversations_v1.py`
- `src/utils/conversations.py`
- `src/models/common/responses/types.py` (if remaining and conversations-owned)
- `tests/unit/app/endpoints/test_conversations.py`
- `tests/unit/utils/test_conversations.py`
- `tests/integration/endpoints/test_conversations_v1_integration.py`

---

## PR12b — Vector stores adaptation

**Summary:** Vector stores endpoint adaptations for OGX 1.0, with tests.  
**Size:** ~130–200 lines

**Files:**

- `src/app/endpoints/vector_stores.py`
- `tests/unit/app/endpoints/test_vector_stores.py`

---

## PR12c — Prompts adaptation

**Summary:** Prompts endpoint adaptations for OGX 1.0, with tests.  
**Size:** ~40–80 lines

**Files:**

- `src/app/endpoints/prompts.py`
- `tests/unit/app/endpoints/test_prompts.py`

---

## PR13 — E2E harness / features

**Summary:** E2E utilities, features, and steps for OGX 1.0 behavior.  
**Size:** ~350–500 lines

**Files:**

- `tests/e2e/utils/llama_stack_utils.py`
- `tests/e2e/utils/utils.py`
- `tests/e2e/utils/README.md`
- `tests/e2e/features/info.feature`
- `tests/e2e/features/llama_stack_disrupted.feature`
- `tests/e2e/features/mcp.feature`
- `tests/e2e/features/skills.feature`
- `tests/e2e/features/steps/common.py`
- `tests/e2e/features/steps/info.py`
- `tests/e2e/rag/README.md`
- `tests/e2e/rag/kv_store.db`
- `tests/e2e/rag/pdf_kv_store.db`

---

## PR14 — OpenAPI artifact regen

**Summary:** Regenerate OpenAPI docs/artifacts after API surface changes.  
**Size:** ~600 lines

**Files:**

- `docs/devel_doc/openapi.json`
- `docs/devel_doc/providers.md`
- `tests/integration/test_openapi_json.py` (if expectations still need updates)

---

## Size outliers (accepted)

| PR | Why over ~1000 lines |
|----|----------------------|
| PR3 Rename | Broad mechanical sweep across many files; trivial to review |
| PR4 Tools | Large rewrite/deletion in `test_tools.py` |
| PR6 Shields | Config model + utils + endpoint + tests together |
| PR7 Streaming | Large rewrite/deletion in `test_streaming_query.py` |

## Checklist before opening each PR

- [ ] Take final behavioral file contents from `bump_lls_to_0.7` tip (not intermediate commits)
- [ ] For PR3: rename-only hunks across the tree; no API rewrites
- [ ] For PR4+: assume PR3 rename already landed; do not redo import/CLI/env renames
- [ ] Include matching unit/integration tests in the same PR as the component
- [ ] Keep intentional shared-file splits to the rows in the ownership table above
