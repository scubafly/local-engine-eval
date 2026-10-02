#!/usr/bin/env python3
"""Isolate what makes the managed llama.cpp lane slow: context size, KV quantisation, or
MTP speculative decoding. One variant at a time, one server resident at a time.

Baseline is the preset Hermes generates itself: ctx 262144, cache q8_0, spec draft-mtp,
measured at 9.8 tok/s median end-to-end against Ollama's MLX engine at 20.4.
"""
import importlib.util, json, os, pathlib, signal, statistics, subprocess, sys, time, urllib.request

SP = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("benchcore", SP / "bench.py")
core = importlib.util.module_from_spec(spec)
sys.modules["benchcore"] = core
# exec only the definitions: bench-engines.py guards its own entry point with __main__
spec.loader.exec_module(core)

SERVER = os.environ["LLAMA_SERVER"]   # path to your llama-server binary
MODEL = os.environ["GGUF_MODEL"]     # path to your .gguf
PORT = 18500
BASE = f"http://127.0.0.1:{PORT}/v1"

VARIANTS = [
    ("V1 ctx 32K · KV q8_0 · spec mtp",
     ["--ctx-size", "32768", "--cache-type-k", "q8_0", "--cache-type-v", "q8_0",
      "--spec-type", "draft-mtp", "--spec-draft-n-max", "2"]),
    ("V2 ctx 32K · KV q8_0 · spec uit",
     ["--ctx-size", "32768", "--cache-type-k", "q8_0", "--cache-type-v", "q8_0"]),
    ("V3 ctx 32K · KV f16 · spec uit",
     ["--ctx-size", "32768"]),
]

COMMON = ["--host", "127.0.0.1", "--port", str(PORT), "--model", MODEL, "--jinja",
          "--flash-attn", "on", "--batch-size", "4096", "--ubatch-size", "2048",
          "--no-webui"]


def wait_health(proc, timeout=420):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=5) as fh:
                if json.loads(fh.read())["status"] == "ok":
                    return True
        except Exception:
            pass
        time.sleep(3)
    return False


for label, flags in VARIANTS:
    print(f"\n######## {label}", flush=True)
    log = open(SP / "variant.log", "w")
    proc = subprocess.Popen([SERVER, *COMMON, *flags], stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True)
    try:
        t0 = time.time()
        if not wait_health(proc):
            print("  server kwam niet op; zie variant.log", flush=True)
            continue
        print(f"  load {time.time()-t0:.0f}s", flush=True)
        core.bench(label, BASE, "Qwen3.8-27B-UD-Q4_K_M")
    finally:
        with open(SP / f"variant-{label.split()[0]}.log", "w") as dst:
            dst.write((SP / "variant.log").read_text())
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(timeout=60)
        time.sleep(5)
