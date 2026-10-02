#!/bin/sh
# Round 2: Ollama's own MLX runner. llama.cpp stays down so only one engine is resident.
set -eu
SP="$(dirname "$0")"
PID=$(pgrep -f "runtimes/llamacpp" | head -1 || true)
[ -n "$PID" ] && kill "$PID" || true
# Start Ollama however it is installed on this machine. The point is only that it is the
# ONLY engine resident while this round runs.
ollama serve >/dev/null 2>&1 &
until curl -sf -m 5 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; do sleep 3; done
echo "ollama op"
python3 "$SP/../run.py" ollama-mlx http://127.0.0.1:11434/v1 "${OLLAMA_MODEL:-qwen3.8:27b-mlx}"
pkill -f "ollama serve" || true
