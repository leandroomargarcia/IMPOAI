# Observability and NCM measurement

This is the live **gold job**, not the default `pytest` suite. Branch tests stay mocked (no OpenAI/Tavily cost). Duty, VAT, and IIBB stay unit tests; they are not scored with an LLM judge.

One gold row = one `app.invoke({question, attempts: 0})` = one trace.

**Order:** these 50 runs are the **NCM v1 baseline** (chapter-first walk in production). Heading retrieval (spec sheet → BM25 → RGI 3) is **v2**, after v1 ships — see `docs/ncm-retrieval.md`. Do not mix v2 into this gold. Build the HTTP API later. OpenTelemetry is for that API, not for these 50 in-process calls.

## Gold set

- **50 product runs**: `question` (as the graph expects it, including CIF) + **verified 8-digit NCM** from the catalog (not eyeballed).
- About **35 typical** products across chapters we care about; about **15 edge** (numeric threshold, residual “las demás”, BK/BIT, mixed/used, chapter boundaries such as tyres 40.11 vs 87.08).
- AFIP/ARCA classification rulings are **not** the v1 gold (they are an edge-case dump, post-MVP). Human corrections later (`question`, predicted NCM, correct NCM) grow the set.

The job is opt-in: `eval/run_gold.py` (not on every commit). Sheet: `eval/gold.json`. How to run and how to read `*.summary.json`: `eval/README.md`.

## What each run records

| Signal | What it answers |
|---|---|
| **Accuracy @ 8 digits** (`accuracy.hit8`) | Exact NCM match = correctness. This is the v1 number that matters for DIE. |
| **Accuracy @ 2 / 4 / 6** | Chapter / heading / subheading. A 90% chapter hit and 40% 8-digit hit means the router is fine and `choose_item` / grade is not. |
| **hit8 by `tag`** | typical vs umbral / residual / frontera / BK / BIT. Global hit8 can hide a 0% on boundaries. |
| **precision8 / recall8** | Same as hit8 unless `ncm_pred` is empty (abstain). Not per-class F1. |
| **Latency p50 / p95** | Wall clock of `invoke` in the summary. Per-node ms still come from Langfuse. |
| **fail_grade / retries** | `grade` false; `attempts` > 1. |
| **Full text per turn** | Every LLM/Tavily call in Langfuse. Store `reporte_final` there, not in the jsonl. |
| **Cost** | OpenAI token USD in Langfuse for that invoke. |

## Consistency (subset)

**10 gold rows × 3 runs**, same `question`. Measure whether the 8-digit NCM stays put. High variance = guessing; overall accuracy can still look fine if it lucks into the gold.

Do not run 50 × 3 by default (cost).

## Where it lives

- **Langfuse** (`CallbackHandler` on live `invoke`, keys in `.env`): one trace per invoke, one span per node, prompt/completion, span duration, tokens. On for gold; off for mocked pytest.
- **Gold JSON / table**: `eval/gold.json` + append-only `eval/results/*.jsonl` (gitignored) and `*.summary.json`. Each jsonl line: gold/pred NCM, `hit2/4/6/8`, `attempts`, `wall_s`. Per-node ms, tokens, and full text stay in Langfuse.
- **Prints** in nodes stay local debug, not the source of truth.

Do not add LangSmith next to Langfuse.

## HTTP API and OpenTelemetry (later)

The 50 gold calls are in-process `graph.invoke`. There is no HTTP server, so they **cannot** measure API latency (queue, auth, JSON, network).

1. **Now:** per-node and total ms from Langfuse spans (and the gold JSON). That is graph time; that is what the 50 calls can teach.
2. **After the office is the product to expose:** wrap the same `invoke` in an HTTP API.
3. **Then:** OpenTelemetry at the **gateway** (rate, errors, duration of the request). Propagate `trace_id` into Langfuse so one user call = one HTTP span + the same graph trace.

Instrumenting OTel before the API duplicates Langfuse on the graph and still leaves gateway latency at zero.

Duty math, hab URL filters, and BCRA fallback stay in mocked pytest; do not fold them into this gold score.
