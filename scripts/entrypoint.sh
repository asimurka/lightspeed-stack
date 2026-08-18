#!/bin/bash
set -e

# Library-mode e2e: restore FAISS fixtures into a writable work path. OGX writes
# on register_vector_store; never use the committed seed DB as the live path.
# Prefer /tmp so UID 1001 can write even with restrictive volume ownership.
RAG_SEED_DIR="${RAG_SEED_DIR:-/opt/app-root/src/.llama/storage/.e2e-rag-seed}"
KV_RAG_PATH="${KV_RAG_PATH:-/tmp/e2e-rag-work/kv_store.db}"
PDF_KV_RAG_PATH="${PDF_KV_RAG_PATH:-/tmp/e2e-rag-work/pdf_kv_store.db}"

if [ -d "$RAG_SEED_DIR" ]; then
    mkdir -p "$(dirname "$KV_RAG_PATH")"
    if [ -f "$RAG_SEED_DIR/kv_store.db" ]; then
        cp -f "$RAG_SEED_DIR/kv_store.db" "$KV_RAG_PATH"
        chmod 664 "$KV_RAG_PATH" 2>/dev/null || true
        sz=$(wc -c <"$KV_RAG_PATH" | tr -d ' ')
        if [ "$sz" -lt 1048576 ]; then
            echo "FATAL: RAG seed kv_store.db too small (${sz} bytes); check tests/e2e/rag" >&2
            exit 1
        fi
        echo "Restored RAG seed -> $KV_RAG_PATH (${sz} bytes)"
    fi
    if [ -f "$RAG_SEED_DIR/pdf_kv_store.db" ]; then
        mkdir -p "$(dirname "$PDF_KV_RAG_PATH")"
        cp -f "$RAG_SEED_DIR/pdf_kv_store.db" "$PDF_KV_RAG_PATH"
        chmod 664 "$PDF_KV_RAG_PATH" 2>/dev/null || true
        echo "Restored PDF RAG seed -> $PDF_KV_RAG_PATH"
    fi
fi

# Only use OpenTelemetry instrumentation if explicitly enabled
# Use explicit venv paths to ensure dependencies are found
if [ "${OTEL_SDK_DISABLED:-true}" = "false" ]; then
    exec /app-root/.venv/bin/opentelemetry-instrument /app-root/.venv/bin/python src/lightspeed_stack.py "$@"
else
    exec /app-root/.venv/bin/python src/lightspeed_stack.py "$@"
fi
