#!/usr/bin/env python3
"""Measure TTFT and decode speed on local endpoints. Streams, so TTFT is real."""
import json, statistics, sys, time, urllib.request

PROMPTS = [
    ("kort", "Noem in één woord de hoofdstad van Nederland."),
    ("code", "Schrijf een Python-functie die een lijst getallen sorteert met insertion sort. Alleen code."),
    ("lang", "Leg in ongeveer 200 woorden uit waarom een MoE-model sneller decodeert dan een dense model."),
]

def run(name, base, model, prompt, max_tokens=400, key=""):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens, "stream": True,
                       "stream_options": {"include_usage": True}}).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(base + "/chat/completions", body, headers)
    t0 = time.perf_counter(); ttft = None; chunks = 0; usage = None
    with urllib.request.urlopen(req, timeout=600) as fh:
        for raw in fh:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                break
            try:
                d = json.loads(payload)
            except Exception:
                continue
            if d.get("usage"):
                usage = d["usage"]
            ch = (d.get("choices") or [{}])[0]
            delta = ch.get("delta") or {}
            if delta.get("content") or delta.get("reasoning_content"):
                chunks += 1
                if ttft is None:
                    ttft = time.perf_counter() - t0
    total = time.perf_counter() - t0
    out_tok = (usage or {}).get("completion_tokens") or chunks
    in_tok = (usage or {}).get("prompt_tokens") or 0
    decode = out_tok / (total - (ttft or 0)) if total > (ttft or 0) else 0
    return {"ttft": ttft or total, "total": total, "in": in_tok, "out": out_tok, "tok_s": decode,
            "e2e": out_tok / total if total else 0}

def bench(label, base, model, runs=2, key=""):
    print(f"\n=== {label} — {model}")
    print(f"{'prompt':6s} {'in':>5s} {'out':>5s} {'TTFT':>7s} {'totaal':>8s} {'e2e':>7s}")
    speeds, ttfts = [], []
    try:
        run("warmup", base, model, "Zeg hallo.", max_tokens=8, key=key)
    except Exception as exc:
        print(f"  niet bereikbaar: {exc}"); return
    for name, prompt in PROMPTS:
        for _ in range(runs):
            try:
                r = run(name, base, model, prompt, key=key)
            except Exception as exc:
                print(f"{name:6s} fout: {exc}"); continue
            print(f"{name:6s} {r['in']:5d} {r['out']:5d} {r['ttft']*1000:6.0f}ms {r['total']:7.2f}s {r['e2e']:7.1f}")
            speeds.append(r["e2e"]); ttfts.append(r["ttft"])
    if speeds:
        print(f"  mediaan e2e {statistics.median(speeds):.1f} tok/s · mediaan TTFT {statistics.median(ttfts)*1000:.0f} ms")

if __name__ == "__main__":
    # One engine resident per half. Running both servers at once is not a fair comparison:
    # 17 GB of weights each on a 64 GB machine means the idle engine still holds unified
    # memory, and decode here is bandwidth-bound, so whichever engine is measured second
    # is systematically handicapped. Caller stops the other server before each half.
    target = sys.argv[1]
    key = sys.argv[2] if len(sys.argv) > 2 else ""
    if target == "llamacpp":
        bench("llama.cpp (Hermes managed) op de M1 Max", "http://127.0.0.1:18434/v1",
              "Qwen3.8-27B-UD-Q4_K_M", key=key)
    elif target == "ollama":
        bench("Ollama 27b-mlx op de M1 Max", "http://127.0.0.1:11434/v1", "qwen3.8:27b-mlx")
    else:
        raise SystemExit("usage: bench-engines.py llamacpp|ollama [api-key]")
