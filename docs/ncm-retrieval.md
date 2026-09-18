# NCM v2 — heading retrieval (after v1 production)

Do **not** implement this until NCM **v1** is gold-tested (50 product runs) and in production. v1 is the chapter-first walk (`pick_chapter` → notes → heading → item → grade). How we score v1: `docs/observability.md`. Hab, price (thread from `START`), and `calc_duty` stay as they are; only the NCM branch changes.

RGI 1: classification is determined by **heading texts and notes**, not chapter titles. v1 inverts that (97 titles, then lock the chapter). v2 retrieves headings from the whole nomenclator, decides among them, then walks 6/8 digits.

Search, in the IR sense, is **only BM25** (step 3). The spec sheet is query understanding; RGI 3 is classification / rerank.

## 0. Index (offline, once)

From `catalog.json`, one document per **heading** (`nivel == 4`):

- code (`84.02`, `40.11`, `87.08`)
- text: heading description, optionally trimmed chapter/section notes
- metadata: chapter (to load full notes after retrieval)

In-memory **BM25** (~1,200 headings). No vector database on day one.

## 1. Input

Same as today: `question` with product + CIF; optional origin, province, VAT status.

Skip retrieval when:

- the question already contains an 8-digit NCM that exists in the catalog → `fetch_ncm` + grade
- numeric thresholds (`20 t/h` vs “superior a 45 t/h”) still use `filter_items` on the item list

## 2. Spec sheet (not search)

A short extraction (rules or one LLM call) that keeps matter / use / presentation and **drops** CIF, origin, brand, quantity, province.

Output: `query_ncm` (the string that hits BM25) plus structured fields. Do not index the raw trade question.

## 3. Search (BM25)

`query_ncm` → top **k = 8** headings from **any** chapter.

The metric that matters here: **recall@8 of the gold 4-digit heading**. If it is not in the list, the LLM cannot recover it.

Keep 2–3 hits even when the first score is far ahead (tyres: 40.11 vs 87.08).

Later, not now: hybrid BM25 + embeddings if lexical search misses synonyms (*caldera* / *generador de vapor*).

## 4. Enrich candidates

For each of the k headings, attach that chapter’s and section’s notes (not leaked duty-table titles). One prompt: spec sheet + RGI 1 and 3 + numbered heading list.

## 5. Heading decision (not search)

One LLM call: pick **one** heading from the shortlist. Do not invent codes.

If two headings fit, RGI 3 in order:

1. most specific
2. essential character
3. last heading number

Chapter is a **consequence** of the winning heading, not a prior lock.

## 6. Descend the tree (reuse v1 nodes)

From that heading:

1. `list_subheadings` when the item list exceeds `ITEM_LIST_LIMIT`
2. `choose_item` + `filter_items`
3. `fetch_ncm` (AIA DIE, BK/BIT, CNCE measures)
4. `grade_ncm` (does this 8-digit item cover the product; notes are exclusions)

Use “las demás” / “los demás” only if no more specific item fits (whisky bottle → 2208.30.20, not .90).

## 7. Retry

v1 retries by returning to `pick_chapter` (same title-list trap).

v2: if grade fails, **drop that heading from the shortlist** and repeat step 5. Re-run BM25 only if the whole top 8 was wrong. Same `MAX_ATTEMPTS` (3).

## 8. Office join

`ncm_done` → hab ∥ duty ∥ `search_price_wait` → report. Hab still routes by chapter (30 ANMAT, 01–05 SENASA), but the chapter comes from the winning heading.

## What we score on v2 (same 50 gold rows)

| Signal | What it answers |
|---|---|
| Recall@8 of the gold heading | Did search work |
| Accuracy @ 4 digits | Did RGI 3 pick the right heading |
| Accuracy @ 6 / 8 | Item / residual |
| Attempts and dropped heading | Whether grade corrects or loops |

Do not use Tavily or the PDF as the classifier. Do not send 97 chapter titles to the model.
