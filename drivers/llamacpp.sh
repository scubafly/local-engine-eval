#!/bin/sh
# Round 1: our own llama-server, MTP off -- the configuration we would actually adopt.
set -eu
SP="$(dirname "$0")"
# Override these for your own install.
SERVER="${LLAMA_SERVER:?set LLAMA_SERVER to your llama-server binary}"
MODEL="${GGUF_MODEL:?set GGUF_MODEL to your .gguf file}"

PID=$(pgrep -f "runtimes/llamacpp" | head -1 || true)
[ -n "$PID" ] && kill "$PID" || true
sleep 5

"$SERVER" --host 127.0.0.1 --port 18500 --model "$MODEL" --jinja --flash-attn on \
    --ctx-size 65536 --cache-type-k q8_0 --cache-type-v q8_0 \
    --batch-size 4096 --ubatch-size 2048 --no-webui >"$SP/../llamacpp-server.log" 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null || true' EXIT

until curl -sf -m 5 http://127.0.0.1:18500/health >/dev/null 2>&1; do
    kill -0 $SRV 2>/dev/null || { echo "server stierf; zie qual-llamacpp-server.log"; exit 1; }
    sleep 3
done
echo "llama.cpp op"
python3 "$SP/../run.py" llamacpp-mtp-uit http://127.0.0.1:18500/v1 Qwen3.8-27B-UD-Q4_K_M
