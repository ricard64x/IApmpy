#!/usr/bin/env bash
# Internal local CPU inference only; do not expose outside Tenonderã's Sprite.
set -euo pipefail
ROOT="${TENONDERA_LLM_ROOT:-/home/sprite/tenondera/local-llm}"
BIN="$ROOT/bin/llama-b12633"
PROFILE="$(cat "$ROOT/profile" 2>/dev/null || echo quality)"
case "$PROFILE" in
  fast)
    MODEL="$ROOT/model/qwen2.5-1.5b-instruct-q4_k_m.gguf"
    MARKER="$ROOT/model/QWEN15_SHA256_VERIFIED"
    EXPECTED="6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e"
    EXPECTED_SIZE=1117320736
    ALIAS="qwen25-1.5b-local"
    THREADS=4
    ;;
  quality)
    MODEL="$ROOT/model/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
    MARKER="$ROOT/model/SHA256_VERIFIED"
    EXPECTED="3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597"
    EXPECTED_SIZE=2497281120
    ALIAS="qwen3-4b-local"
    THREADS=5
    ;;
  *) echo "Unknown model profile" >&2; exit 2 ;;
esac
TOKEN="$ROOT/api-token.txt"
test -x "$BIN/llama-server"
test -f "$MODEL"
test -r "$TOKEN"
test "$(stat -c %s "$MODEL")" = "$EXPECTED_SIZE"
test "$(cat "$MARKER")" = "$EXPECTED"
test "$(stat -c %a "$TOKEN")" = "600"
export LD_LIBRARY_PATH="$BIN${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$BIN/llama-server" \
  --model "$MODEL" \
  --alias "$ALIAS" \
  --host "127.0.0.1" \
  --port 18080 \
  --api-key-file "$TOKEN" \
  --ctx-size 8192 \
  --threads "$THREADS" \
  --threads-batch "$THREADS" \
  --parallel 1 \
  --batch-size 256 \
  --ubatch-size 128 \
  --no-webui
