#!/usr/bin/env bash
# Internal local CPU inference only; do not expose outside Tenonderã's Sprite.
set -euo pipefail
ROOT="${TENONDERA_LLM_ROOT:-/home/sprite/tenondera/local-llm}"
BIN="$ROOT/bin/llama-b12633"
MODEL="$ROOT/model/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
TOKEN="$ROOT/api-token.txt"
MARKER="$ROOT/model/SHA256_VERIFIED"
EXPECTED="3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597"
test -x "$BIN/llama-server"
test -f "$MODEL"
test -r "$TOKEN"
test "$(stat -c %s "$MODEL")" = "2497281120"
test "$(cat "$MARKER")" = "$EXPECTED"
test "$(stat -c %a "$TOKEN")" = "600"
export LD_LIBRARY_PATH="$BIN${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$BIN/llama-server" \
  --model "$MODEL" \
  --alias "qwen3-4b-local" \
  --host "127.0.0.1" \
  --port 18080 \
  --api-key-file "$TOKEN" \
  --ctx-size 8192 \
  --threads 5 \
  --threads-batch 6 \
  --parallel 1 \
  --batch-size 256 \
  --ubatch-size 128 \
  --no-webui
