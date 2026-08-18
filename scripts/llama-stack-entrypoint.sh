#!/bin/bash
# Entrypoint for llama-stack container.
# Enriches config with lightspeed dynamic values, then starts llama-stack.

set -e

INPUT_CONFIG="${LLAMA_STACK_CONFIG:-/opt/app-root/run.yaml}"
ENRICHED_CONFIG="/tmp/enriched-run.yaml"
LIGHTSPEED_CONFIG="${LIGHTSPEED_CONFIG:-/opt/app-root/lightspeed-stack.yaml}"

# Pristine e2e FAISS fixtures (read-only mount). OGX must write metadata on
# register_vector_store, so never point KV_RAG_PATH at the committed files.
# Work copies live under /tmp so UID 1001 can write even when the llama-storage
# named volume has restrictive ownership (common with rootless Podman).
RAG_SEED_DIR="${RAG_SEED_DIR:-/opt/app-root/src/.llama/storage/.e2e-rag-seed}"
KV_RAG_PATH="${KV_RAG_PATH:-/tmp/e2e-rag-work/kv_store.db}"
PDF_KV_RAG_PATH="${PDF_KV_RAG_PATH:-/tmp/e2e-rag-work/pdf_kv_store.db}"

restore_rag_seed() {
    # Re-copy seed DBs into the writable work path on every start so OGX
    # registration cannot permanently empty the e2e fixture (Prow does the same).
    if [ ! -d "$RAG_SEED_DIR" ]; then
        return 0
    fi
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
}

restore_rag_seed

# Enrich config if lightspeed config exists
if [ -f "$LIGHTSPEED_CONFIG" ]; then
    echo "Enriching llama-stack config..."
    ENRICHMENT_FAILED=0
    /opt/app-root/.venv/bin/python3 /opt/app-root/llama_stack_configuration.py \
        -c "$LIGHTSPEED_CONFIG" \
        -i "$INPUT_CONFIG" \
        -o "$ENRICHED_CONFIG" 2>&1 || ENRICHMENT_FAILED=1

    if [ -f "$ENRICHED_CONFIG" ] && [ "$ENRICHMENT_FAILED" -eq 0 ]; then
        echo "Using enriched config: $ENRICHED_CONFIG"
        # Re-seed after enrichment in case anything touched the work DB.
        restore_rag_seed
        # OGX 1.2.0+ requires TLS or --insecure for local/e2e plain HTTP (not 1.3-only).
        exec ogx stack run --insecure "$ENRICHED_CONFIG"
    fi
fi

echo "Using original config: $INPUT_CONFIG"
restore_rag_seed
exec ogx stack run --insecure "$INPUT_CONFIG"
