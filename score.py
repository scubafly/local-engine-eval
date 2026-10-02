"""Score the saved generations. Deterministic: tests are executed, JSON is parsed and
validated against the schema, constraints are matched by regex, recall is exact match.

Code answers run in a subprocess with a timeout. That is still arbitrary model-written code
executing locally, so it runs with no arguments, no network use of its own, and a hard
10-second limit -- enough for these functions, short enough that a runaway loop cannot stall
the scoring. Anything that raises, times out, or fails an assert scores 0.
"""
import importlib.util, json, os, pathlib, re, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("qt", HERE / "tasks.py")
qt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qt)
# Scored per language: a result file records the language it ran in, and the expected answers
# differ ("Parijs" against "Paris", "JA" against "YES"). Scoring every file against one
# language marks correct answers wrong, which is exactly what happened on the first English run.
TASKS_BY_LANG = {lang: {t["id"]: t for t in qt.build(lang)} for lang in ("nl", "en")}

FENCE = re.compile(r"```(?:python|json)?\s*(.*?)```", re.S)


def unfence(text):
    hit = FENCE.search(text)
    return hit.group(1).strip() if hit else text.strip()


def score_code(task, answer):
    code = unfence(answer)
    if not code:
        return 0, "leeg"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(code + "\n\n" + task["tests"])
        path = fh.name
    try:
        p = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        return 0, "timeout"
    if p.returncode == 0:
        return 1, "tests ok"
    last = (p.stderr or "").strip().splitlines()
    return 0, (last[-1][:60] if last else "exit %d" % p.returncode)


def score_json(task, answer):
    raw = unfence(answer)
    try:
        d = json.loads(raw)
    except Exception:
        return 0, "geen valide JSON"
    if not isinstance(d, dict):
        return 0, "geen object"
    missing = [k for k in ("title", "priority", "labels") if k not in d]
    if missing:
        return 0, "mist " + ",".join(missing)
    if not isinstance(d["title"], str) or not isinstance(d["labels"], list):
        return 0, "verkeerde types"
    if not all(isinstance(x, str) for x in d["labels"]):
        return 0, "labels niet alle string"
    if d["priority"] not in ("low", "normal", "high"):
        return 0, "priority buiten enum"
    if "estimate" in d and not isinstance(d["estimate"], (int, float)):
        return 0, "estimate geen getal"
    # Schema-conform is the pass mark; the right priority is reported separately, because
    # picking it is judgement rather than format compliance.
    return 1, ("priority juist" if d["priority"] == task["priority"]
               else f"priority {d['priority']} i.p.v. {task['priority']}")


def score_constraint(task, answer):
    ok = re.match(task["pattern"], answer) is not None
    return (1, "ok") if ok else (0, repr(answer[:50]))


def score_recall(task, answer):
    ok = task["answer"].lower() in answer.lower()
    return (1, "ok") if ok else (0, repr(answer[:50]))


SCORERS = {"code": score_code, "json": score_json,
           "constraint": score_constraint, "recall": score_recall}

rows = {}
results_dir = pathlib.Path(os.environ.get("EVAL_OUT", HERE / "results"))
for path in sorted(results_dir.glob("*.json")):
    doc = json.loads(path.read_text())
    label = doc["label"]
    TASKS = TASKS_BY_LANG[doc.get("lang", "nl")]
    per_kind, notes, cut = {}, [], []
    for r in doc["results"]:
        task = TASKS[r["id"]]
        if r["error"]:
            pts, note = 0, "call faalde"
        elif r.get("finish") == "length":
            # Not a quality failure: the answer never finished inside the token budget.
            pts, note = 0, "AFGEKAPT op max_tokens"
        else:
            pts, note = SCORERS[task["kind"]](task, r["answer"])
        per_kind.setdefault(task["kind"], []).append(pts)
        if r.get("finish") == "length":
            cut.append(r["id"])
        if pts == 0 or "i.p.v." in note:
            notes.append(f"{r['id']}: {note}")
    rows[label] = (per_kind, notes, doc["model"],
                   sum(r["secs"] for r in doc["results"]), cut)

kinds = ["code", "json", "constraint", "recall"]
print(f"{'engine':34s} " + " ".join(f"{k:>11s}" for k in kinds) + f" {'totaal':>8s} {'tijd':>8s}")
for label, (per_kind, notes, model, secs, cut) in rows.items():
    cells, tot, mx = [], 0, 0
    for k in kinds:
        got, n = sum(per_kind.get(k, [])), len(per_kind.get(k, []))
        cells.append(f"{got}/{n}".rjust(11))
        tot += got
        mx += n
    print(f"{label:34s} " + " ".join(cells) + f" {f'{tot}/{mx}':>8s} {secs/60:7.1f}m"
          + (f"  ({len(cut)} afgekapt)" if cut else ""))

for label, (_, notes, _, _, _) in rows.items():
    if notes:
        print(f"\n-- {label}")
        for n in notes:
            print("   " + n)
