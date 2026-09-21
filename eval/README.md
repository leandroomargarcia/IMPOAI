# Gold eval (NCM v1 baseline)

Live job, not default `pytest`. Sheet: `eval/gold.json` (50 rows). Runner: `eval/run_gold.py`.

The v1 number to report is **`accuracy.hit8`** (exact 8-digit match = correctness). Hierarchical `hit2` / `hit4` / `hit6` show where the walk breaks. `precision8` and `recall8` equal `hit8` unless a row has an empty `ncm_pred`. Do not compute per-NCM F1. BM25 recall@k is v2 (`docs/ncm-retrieval.md`).

## Run (from the IMPOAI root)

```powershell
.\.venv\Scripts\python.exe eval\run_gold.py --limit 1 --id olive-virgin
.\.venv\Scripts\python.exe eval\run_gold.py --limit 5
.\.venv\Scripts\python.exe eval\run_gold.py --limit 50 --out eval\results\v1-full.jsonl
```

The jsonl is **appended**. After a live batch the summary is computed from the **whole** `--out` file, not only the new rows. Use a new `--out` (or delete the file) for a clean 50-row file.

Score an existing jsonl without calling OpenAI:

```powershell
.\.venv\Scripts\python.exe eval\run_gold.py --from-jsonl eval\results\v1.jsonl
```

Writes `eval/results/v1.summary.json` (same stem as the jsonl). `eval/results/` is gitignored.

## Summary fields

| Field | Meaning |
|---|---|
| `accuracy.hit8` | v1 correctness / DIE-relevant accuracy |
| `accuracy.hit2/4/6` | chapter / heading / subheading |
| `by_tag.*.hit8` | typical vs umbral / residual / frontera / … |
| `precision8` / `recall8` | same as hit8 if every row predicted a code |
| `latency_s.p50` / `p95` | wall clock of `invoke` |
| `fail_grade` | rows with `grade` false |
| `retries` | rows with `attempts` > 1 |

Consistency (10 gold ids × 3) is a later pass; do not run 50 × 3.

How this job fits Langfuse and the 50-row protocol: `docs/observability.md`.
