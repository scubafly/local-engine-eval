# Results — Qwen3.8-27B on Apple silicon, 2026-10-02

One model family, five engine-and-quantisation combinations, measured in a single sitting.
The short version: **quality was indistinguishable, so the decision came down to speed, and
speculative decoding lost on every engine that offered it.**

Hardware: MacBook Pro M1 Max, 64 GB, macOS 27.0. One engine resident per measurement, with
`vm.swapusage` checked before and after each round (it never moved during a round). Splash runs
on a second machine, an M5 Pro, so its timings are not comparable with the rest — only its
quality scores are.

## Speed

Median end-to-end tokens per second (output tokens over total wall time, which the thinking
phase cannot inflate) and median streamed time-to-first-token, over six requests across three
prompt shapes.

| engine | quantisation | decode | TTFT |
|---|---|---|---|
| Splash *(on an M5 Pro — different machine)* | UD-Q4_K_M | 53.0 | 189 ms |
| Ollama, its own MLX runner | Ollama 4-bit MLX | **20.4** | 5245 ms |
| mlx-lm (Apple) | MLX 4-bit | 16.7 | n/a, does not stream incrementally |
| MTPLX, autoregressive | dynamic 4-bit | 14.2 | 931 ms |
| llama.cpp, MTP off | UD-Q4_K_M | 12.9 | **368 ms** |
| MTPLX, native MTP depth 3 | dynamic 4-bit | 12.1 | 1481 ms |
| llama.cpp, MTP on (stock Hermes preset) | UD-Q4_K_M | 9.8 | 495 ms |

Decode throughput is not the whole story, because time-to-first-token is paid once per request
and an agent makes many short requests. Per step, on this machine:

| output length | llama.cpp (0.37 s + 12.9 t/s) | Ollama (5.2 s + 20.4 t/s) |
|---|---|---|
| 50 tokens | **4.3 s** | 7.7 s |
| 150 tokens | **12.0 s** | 12.6 s |
| 400 tokens | 31.4 s | **24.8 s** |

The crossover sits near 190 output tokens. Short tool-calling steps favour llama.cpp; long
prose favours the MLX runner.

## What does *not* matter: context size and KV quantisation

Isolated one factor at a time on llama.cpp:

| context | KV cache | speculative | decode |
|---|---|---|---|
| 262144 | q8_0 | draft-mtp | 9.8 |
| 32768 | q8_0 | draft-mtp | 9.8 |
| 32768 | q8_0 | off | 12.6 |
| 32768 | f16 | off | 12.9 |

Dropping the window from 256K to 32K changed nothing at all. Quantising the KV cache to `q8_0`
costs 2%, so it is nearly free. Turning speculative decoding off gained 29%.

## Speculative decoding lost, three times over

| engine | with drafting | without | effect |
|---|---|---|---|
| llama.cpp `--spec-type draft-mtp --spec-draft-n-max 2` | 9.8 | 12.6 | **−22%** |
| MTPLX native MTP, depth 3 | 12.1 | 14.2 | **−15%** |

MTPLX ships a tuner, and it disagrees with the measurement above: `mtplx tune` reports AR at
14.4 and depth 3 at 34.1 tok/s, a 2.37x gain. That 34 was not reproducible through the HTTP API
on any workload tried. Streaming is not the cause (streamed and non-streamed were within 3% of
each other), and six identical back-to-back requests held steady between 9.8 and 11.3 tok/s with
no thermal warning recorded.

Drafting gain does depend on how predictable the output is, which is the expected shape — a
draft only pays off when the verification pass accepts it:

| task | decode | reasoning tokens |
|---|---|---|
| copy a block of code verbatim | 19.9 | 31 |
| copy it back with one mechanical change | 11.2 | 77 |
| write new prose | 9.7 | 699 |

So the published 2–3x figures are plausible for their best case on their hardware — MTPLX's own
numbers come from an M5 Max, and `mtplx hardware` reports `M5 TensorOps eligible: false` for an
M1 Max. On this machine, drafting costs more than it returns, including for the realistic
"rewrite a file with a small change" case that an agent spends most of its tokens on.

## Quality

30 tasks, scored deterministically. Dutch and English runs of the two language-sensitive
categories are reported separately.

| engine | code | json | constraint | recall | total |
|---|---|---|---|---|---|
| llama.cpp, MTP off | 9/10 | 10/10 | 5/5 | 5/5 | 29/30 ¹ |
| Ollama MLX runner | 9/10 | 10/10 | 5/5 | 5/5 | 29/30 |
| Splash (M5 Pro) | 9/10 | 10/10 | 5/5 | 5/5 | 29/30 ¹ |
| mlx-lm (Apple) | 7/10 | 10/10 | 5/5 | 5/5 | 27/30 ² |

¹ one task truncated at the token budget rather than answered wrongly
² three tasks truncated; mlx-lm spent the most tokens reasoning

English subset (json + constraint, 15 tasks): llama.cpp, Ollama, mlx-lm, MTPLX and Splash each
scored **15/15**.

There is no quality signal here to choose on. Every engine produced schema-valid tool calls,
obeyed every hard output constraint, and found every planted fact in a 12K-token document, in
both languages. The only genuine wrong answer in the whole matrix was one `AssertionError` from
Ollama on a code task. Every other lost point is a truncation, which measures the budget rather
than the model.

Two caveats worth keeping in mind before reusing these numbers:

- The engines ship different quantisations of the same weights (15.70 GB UD-Q4_K_M, 16.05 GB MLX
  4-bit, 16.93 GB Ollama, 19.28 GB MTPLX dynamic 4-bit). A truly weights-identical comparison is
  not possible: llama.cpp reads only GGUF, MLX only its own format.
- Dutch prompts are the more sensitive probe, because the model reasons in English regardless and
  quantisation damages less-represented languages first. That the Dutch scores match the English
  ones is therefore the stronger result, not the weaker one.

## Reproducing

Every number here comes from `bench.py`, `bench-variants.py` and `run.py` + `score.py` in this
repository; the raw generations are in `results/`, one JSON per engine and language, including
`finish_reason` and token counts per task so a score can be audited without rerunning anything.
