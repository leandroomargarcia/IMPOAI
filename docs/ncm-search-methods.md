# NCM search methods (after v1)

v1 is a greedy top-down walk: `pick_chapter` → notes → heading → item → grade. Each choice is final. The gold run shows where that breaks: **hit4 94 %, hit6 80 %, hit8 72 %**. The walk finds the right area of the nomenclator; it loses the last split (subheading, item, "las demás", BIT).

So the lever is **how we walk the tree**, not a new search engine. BERT fine-tuning and generic PDF RAG are out: 50 gold rows cannot train ~1,200 classes, and the PDF is not aligned by heading. Heading BM25 (`docs/ncm-retrieval.md`) stays an option for heading misses.

## 1. Bottom-up: search the 8-digit items

Search the items, not the 97 chapter titles. Each item already carries its full path in `descripcion_completa` ("Café… / Sin descafeinar / En grano"). That text holds the words that decide the 8th digit ("en grano", "acuotubular", "simplemente canchada").

1. Lexical search over items → top 20.
2. Group by heading.
3. The LLM picks among real items, with each full path in the prompt.

Targets hit6 and hit8 directly.

## 2. Beam search instead of greedy

Same tree, but keep 2–3 paths per level instead of one. The grader compares the leaves at the end. A wrong first heading no longer kills the right path.

Today a retry re-picks the chapter from the same 97 titles (the same trap).

## 3. HS6 first, then the Mercosur split

NCM = HS 6 digits (international) + 2 Mercosur digits. LLMs know HS6 reasonably well.

1. The LLM proposes 2–3 HS6 codes.
2. The catalog checks they exist (nothing invented).
3. Choose the 8-digit item only among their real children.

Skips the 97-title step entirely.

## 4. Ask when the decisive attribute is missing

A broker asks before guessing. If the subheading depends on something the user did not say (material, use, capacity, roasted or not), detect it from the tree options and ask in the chat. Many 8th-digit misses (BIT, "las demás") are missing input, not bad search. Fits the existing chat slots.

## Order

Try **1 + 2 first**: one experiment on the existing catalog, no new models, scored on the same 50 gold rows (hit6 / hit8 vs 72 %). Add 4 later; it changes the product, not only the classifier.

## Before choosing: read the 14 misses

| Most misses are… | Try |
|---|---|
| item / 8th digit | 1 + 2 |
| heading (e.g. 40.11 vs 87.08) | 3, or heading BM25 |
| missing info in the question | 4 |

## How to record an experiment

No MLflow: nothing is trained. Each method runs on its own branch and is scored with the same gold job:

```powershell
.\.venv\Scripts\python.exe eval\run_gold.py --limit 50 --method items-beam --param beam=3 --param top_items=20
```

`--method` becomes a Langfuse tag; method, params, branch, and commit go into trace and score metadata. Compare methods by hit6 / hit8 against `v1-chapter-first`. Details: `eval/README.md`.
