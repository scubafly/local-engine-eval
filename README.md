# engine-eval — comparing local inference engines on the same model

Built on 2026-10-02 to answer a concrete question: Hermes runs the developer role on a local
27B model, and we wanted to know which engine to serve it with, on quality as well as speed.
The answer turned out to depend on both, in opposite directions, so both are measured here.

Two independent harnesses:

- `bench.py` — speed. Streams, so time-to-first-token is real rather than inferred.
- `tasks.py` + `run.py` + `score.py` — quality. Deterministic scoring, no judge model.

## Method, and why it is shaped this way

**One engine resident at a time.** Two engines holding 16 GB of weights each on a 64 GB
machine pushes the page cache into swap, and decode on Apple silicon is memory-bandwidth
bound, so whichever engine is measured second is systematically handicapped. The drivers stop
the other server before they start. Check `sysctl vm.swapusage` before and after a run: if the
number moves, the run is contaminated. Note that `used` does not fall when pressure ends, so
what matters is whether it *changes*, not its absolute value.

**End-to-end tokens per second, not the engine's own counter.** Ollama withholds the thinking
phase and then emits it in one block, which makes a naive decode measurement report hundreds
of tokens per second. Output tokens divided by total wall time cannot be gamed that way.

**Token budgets sized for a thinking model.** Qwen3.8 bills its reasoning block against
`max_tokens`. A budget sized for the answer alone returns `finish_reason: "length"` with empty
content, which silently scores as a wrong answer. Measured: a one-line "name three colours"
task needs 393 tokens, not 120. `run.py` records `finish_reason` and `score.py` reports those
cases as `AFGEKAPT` instead of scoring them, because a truncated answer measures the budget,
not the model. This mistake invalidated a first full run; the flag exists so it cannot happen
quietly again.

**Deterministic scoring.** Four shapes, each checkable without a judge, so the eval costs
nothing to run and reproduces:

| kind | what it measures | how it is scored |
|---|---|---|
| `code` (10) | can it write a working function | the asserts are executed |
| `json` (10) | tool-call discipline against a fixed schema | parsed and validated; wrong `priority` is reported separately from a format failure, because picking it is judgement rather than compliance |
| `constraint` (5) | obeying a hard output format | regex |
| `recall` (5) | finding one planted fact in ~12K tokens | exact match |

Quantisation damage tends to show up in `json` and `constraint` before it shows up anywhere
else, which is why they are separate columns rather than folded into one score.

`temperature` is 0 everywhere, and the thinking channel is stripped before scoring so the
scorers see the answer a caller would act on.

## Safety note

`score.py` executes model-written code to check it. That runs locally in a subprocess with a
10-second limit and no arguments; a hang or an exception scores 0 rather than stalling the
scoring. It is still arbitrary generated code, so run it on a machine where that is acceptable.

## Running it

```sh
# speed, one engine at a time
python3 bench.py llamacpp "$API_KEY"
python3 bench.py ollama

# quality: generate, then score. Results land in ./results/<label>.json (EVAL_OUT overrides).
./drivers/llamacpp.sh                  # own llama-server, MTP off, port 18500
./drivers/ollama.sh                    # Ollama's MLX runner
python3 run.py splash http://<other-host>:8000/v1 unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_M
python3 score.py
```

Generations are saved per task as they complete, so a run can be inspected while it is still
going and re-scored later without regenerating — which matters, because a full round is tens
of minutes.

## Reading the output

Scores are comparable across engines only when the engines ran on the same machine. A round
against an engine on another Mac is useful for the quality columns and meaningless for the time
column. Engines also ship different quantisations of the same weights, so a quality gap is a
gap between *engine plus quant as you would actually run it*, not between engines on identical
weights. That comparison is not available: llama.cpp reads only GGUF, MLX only its own format.
