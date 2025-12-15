#!/bin/bash
# Entrypoint for llama-stack container.
# Enriches config with lightspeed dynamic values, then starts llama-stack.

set -e

INPUT_CONFIG="${LLAMA_STACK_CONFIG:-/opt/app-root/run.yaml}"
ENRICHED_CONFIG="/tmp/run_enriched.yaml"
LIGHTSPEED_CONFIG="${LIGHTSPEED_CONFIG:-/opt/app-root/lightspeed-stack.yaml}"

# Enrich config if lightspeed config exists
if [ -f "$LIGHTSPEED_CONFIG" ]; then
    echo "Enriching llama-stack config..."
    python3 /opt/app-root/enrich_llama_config.py \
        -c "$LIGHTSPEED_CONFIG" \
        -i "$INPUT_CONFIG" \
        -o "$ENRICHED_CONFIG" 2>&1 || true

    if [ -f "$ENRICHED_CONFIG" ]; then
        echo "Using enriched config: $ENRICHED_CONFIG"
        exec llama stack run "$ENRICHED_CONFIG"
    fi
fi

echo "Using original config: $INPUT_CONFIG"
exec llama stack run "$INPUT_CONFIG"

