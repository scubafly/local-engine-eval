"""Run the quality tasks against one OpenAI-compatible endpoint and save the raw answers.

Scoring is a separate step on purpose: the generations are expensive (one engine resident at
a time, model loads in between), so they are kept on disk and can be re-scored without
regenerating. Temperature 0, and the thinking channel is stripped before saving so the
scorers see the answer the caller would act on.
"""
import importlib.util, json, os, pathlib, re, sys, time, urllib.error, urllib.request

HERE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("qt", HERE / "tasks.py")
qt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qt)

THINK = re.compile(r"<think>.*?</think>\s*", re.S)


def ask(base, model, prompt, max_tokens, key=""):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens, "temperature": 0, "stream": False}).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(base + "/chat/completions", body, headers)
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=900) as fh:
        d = json.load(fh)
    choice = (d.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    text = msg.get("content") or ""
    # finish_reason is recorded because a thinking model spends max_tokens on the reasoning
    # block first: a budget that is too small returns "length" with empty content, which must
    # be reported as a truncated measurement rather than scored as a wrong answer.
    return (THINK.sub("", text).strip(), time.perf_counter() - t0,
            choice.get("finish_reason"), (d.get("usage") or {}).get("completion_tokens"))


if __name__ == "__main__":
    label, base, model = sys.argv[1], sys.argv[2], sys.argv[3]
    key = sys.argv[4] if len(sys.argv) > 4 else ""
    out = pathlib.Path(os.environ.get("EVAL_OUT", HERE / "results")) / f"{label}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    results = []
    for i, task in enumerate(qt.build(), 1):
        try:
            answer, secs, finish, used = ask(base, model, task["prompt"], task["max_tokens"], key)
            err = None
        except Exception as exc:  # noqa: BLE001 -- a failure is a result: it scores as wrong
            answer, secs, err, finish, used = "", 0.0, f"{type(exc).__name__}: {exc}", None, None
        results.append({"id": task["id"], "kind": task["kind"], "answer": answer,
                        "secs": round(secs, 2), "error": err, "finish": finish, "used": used})
        flag = "FOUT: " + err if err else ("AFGEKAPT" if finish == "length" else "")
        print(f"  {i:2d}/30 {task['id']:9s} {secs:6.1f}s {str(used or '-'):>5s} tok {flag}", flush=True)
        out.write_text(json.dumps({"label": label, "model": model, "results": results}, indent=1))
    print(f"opgeslagen in {out}")
