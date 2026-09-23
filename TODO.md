# TODO — IMPOAI

Done: 97-chapter NCM catalog (JSON, not RAG). Office: `search_price_start` at START (thread); NCM walk; then hab ∥ duty ∥ `search_price_wait` → join → report.

## Full catalog

- [x] Parse all 97 PDF chapters (drop `POC_CHAPTERS = {1, 9}`)
- [x] Reset hierarchy when the heading changes (`0903.00` with no `09.03`)
- [x] Accept AEC with `BK` / `BIT` flags
- [x] Skip the aeronautical table
- [x] Attach section and subheading notes to the chapter
- [x] Generate `ncm/data/catalog.json` (once, offline)
- [x] Audit the JSON: 97 chapters, 8-digit items, parent path, null AEC
- [x] POC regression: `0901.11.10`, `0101.21.00`, `0903.00.10`
- [x] Spot-check chapters 27, 39, 84
- [x] If a heading has many items, list 6-digit subheadings first



## Graph

- [x] Fill NCM-branch `GraphState` (`ncm_chapter`, `ncm_notes`, `ncm_heading`, `ncm_item`, `ncm`, `ncm_aec`, `ncm_feedback`, `ncm_info`, …)
- [x] Split `clasificar_ncm` into nodes: router → notes → heading → item → `get_ncm` → grade
- [x] If `get_ncm` fails, do not call the grader
- [x] If the budget is spent without grounding, `ncm_info` must say it did not classify
- [x] Wire the office: `search_price_start` at START (background Tavily); NCM walk; then hab ∥ duty ∥ `search_price_wait` → join → report. Hab does not search generic `.gob.ar`: needs a keyword or chapter organism (01–05 SENASA, 30 ANMAT).
- [x] Filter items whose numeric threshold (e.g. 20 t/h vs over 45 t/h) contradicts the question; the grader also rejects without an LLM
- [x] Hab: drop used-goods / C.I.B.U.I.H. hits unless the question asks for used
- [x] Hab: drop SENASA / ANMAT / ANMaC if the product is not that organism
- [x] Test 3 products outside chapters 1 and 9 (live ibuprofen / tricycle runs happened; no fixed test)



## What a broker uses and we still lack

- [x] **NESH** — closed: the WCO book is not free; no NESH index in the repo
- [ ] **AFIP/ARCA classification rulings** — **very low priority (post-MVP)**. They cover edge cases, not the general flow. If done, they go after `get_ncm` as validation (not as the classifier). Needs a dump of RG annexes (ARCA library); the AIA nomenclator is not this.

Spec sheet and RGI 3 across headings are **NCM v2** (`docs/ncm-retrieval.md`). Do not start them until v1 is gold-tested and in production.


## NCM classifier versions

**v1 (now) — baseline.** Chapter-first walk: `pick_chapter` → notes → heading → optional 6-digit → item → card → grade (max 3 retries). This is what we measure and ship.

- [x] **Baseline gold: 50 product runs** on this architecture. Sheet `eval/gold.json`. Live job: `eval/run_gold.py --limit 50 --out eval/results/v1-langfuse.jsonl`. v1 score: **hit8 72 %** (hit2/4 94 %, hit6 80 %, p50 5.2 s). 14 misses (yerba empty, BIT 8th digit, milk-powder, …). Not AFIP criterios.
- [ ] **Ship v1** after consistency (10×3) if we still want it; production stays on this walk.

**v2 (after v1 is in production).** Do not mix this into the 50 baseline runs. Method: `docs/ncm-retrieval.md`.

- [ ] Spec sheet (composition, use, presentation) then BM25 over **headings** (level 4), not 97 chapter titles
- [ ] LLM picks among k heading candidates using notes + RGI 3 (more specific / essential character / last number); then the existing 6/8 descent + grade
- [ ] Retry drops the failed heading from the shortlist (does not re-roll `pick_chapter` from titles)
- [ ] Re-run the same 50 gold rows vs v1 (plus recall@8 of the gold heading in the BM25 list)



## Broker-style liquidation (simulate, do not replace AFIP)

Today `calc_duty` does `CIF × DIE%` + statistical fee + CNCE measures + **VAT** + **VAT perception** + **income-tax perception** + **IIBB** (if a province is given). Still not a filing.

### Change what is already there

- [x] Base = user-entered **CIF** (chat will ask for it later)
- [x] `impuestos_estimados` is an **estimated liquidation total** (DIE + statistical fee + measures + VAT + perceptions + IIBB)
- [x] Fill `costos_asociados` with a **line-by-line breakdown** (CIF, DIE, statistical fee, measures, VAT, perceptions, IIBB)
- [x] State explicitly in the report that this is an **estimate**, not a SIM / María declaration
- [x] The tax node stays **arithmetic + tables**, not an LLM or a ReAct agent



### Duties and fees (on CIF)

- [x] Parse the Arancel Integrado dump (`docs/nomenclador_*.txt`) and use current DIE as AEC in `get_ncm`
- [x] **AEC / import duty** — apply the rate on CIF
- [x] **Specific**, antidumping, or safeguard duties: CNCE xlsx lookup by NCM; add ad valorem if origin is given; specific / min FOB are reported, not liquidated. This dump has no safeguards
- [x] Liquidate **specific** when the user gives quantity/unit and the spreadsheet has **one** rate (origin + unit match). If there are several (dry vs steam) or it is min FOB, only warn
- [x] **Statistical fee** — 3 % of CIF (Decreto 1140/2024), with USD caps and 0 if origin is Mercosur. Do not use the nomenclator RE column (that is not this fee)
- [x] Use catalog `BK` / `BIT` flags: legend in the breakdown and 10.5 % VAT (not an extra duty; DIE already comes from AIA)



### VAT and AFIP perceptions

- [x] **VAT** 21 % default on CIF + DIE + statistical fee + measures. If the NCM is **BK/BIT**, 10.5 % (assumes productive use). Food/medicine 10.5 % NCM table: still missing. The user can put `IVA 10.5` (or `IVA exento` / `IVA 21`) in the question
- [x] **VAT perception (additional)** — RG 2937/4461: 20 % if VAT is 21 %, 10 % if VAT is 10.5 %, same base. 0 if VAT-exempt. Credit for the registered taxpayer
- [x] **Income-tax perception** — RG 2281: 11 % monotributista (**default**), 6 % if the question says `responsable inscripto`, 3 % `responsable inscripto CVDI`, 11 % personal use, 0 with an exclusion certificate. Base: CIF + DIE + statistical fee + measures (no VAT, art. 6)
- [x] Store in state whether the user is **inscripto** (default no / monotributista; they must say `responsable inscripto`)



### IIBB

- [x] Do not use a national %. Ask for **provincia** (or `IIBB 3.5` by hand) and apply that jurisdiction's estimated general rate (budget SIRPEI table; not the CUIT factor)
- [x] Default 0 if the user does not give a province



### Operating costs (after the customs liquidation)

Closed: IMPOAI does not estimate these. The report warns that CIF + fiscal duties is not a landed cost.

- [x] Customs-broker fees, bonded warehouse / terminal, inland freight, local insurance — out of scope (despachante / terminal / forwarder quote them)
- [x] **Habilitations (SENASA/ANMAT, etc.)** — list procedures, not amounts; the same report note covers permit tariffs



### Local price / FX (already started)

- [x] **USD/ARS rate** — BCRA Comunicación A 3500 (`api.bcra.gob.ar/estadisticascambiarias`, `tipoCotizacion` USD). Only converts shelf ARS→USD. If the API fails, `USD_ARS_RATE` 1535 and the report says so.
- [ ] Compare **CIF + estimated liquidation** against `precio_ref` (local sale in USD)



## Observability

How we measure: `docs/observability.md`. Default pytest stays mocked. Gold + traces are a separate live job. **These 50 runs score NCM v1 (chapter-first walk).** HTTP API and OpenTelemetry come after. Heading retrieval (v2) is `docs/ncm-retrieval.md` and waits until v1 is in production.

- [x] **Gold set (50 product runs)** — v1 baseline recorded (`eval/gold.json`, `eval/results/v1-langfuse.jsonl`). ~35 typical, ~15 edge. Not AFIP criterios.
- [x] **Hierarchical accuracy** — `eval/run_gold.py` writes `*.summary.json` (`accuracy.hit2/4/6/8`, `by_tag`, `precision8`/`recall8`, p50/p95). Protocol: `eval/README.md`. Recorded: hit8 **72 %**.
- [x] **Latency** — `wall_s` on each gold row + Langfuse span ms. Price thread from `search_price_start`; `load_notes` does not wait on Tavily.
- [x] **Retries per node** — in the jsonl (`attempts`) and summary (`retries` / `fail_grade`: 4 / 4 on this run).
- [x] **Full text per turn** — Langfuse trace per invoke (prompts, Tavily, `reporte_final`).
- [x] **Cost** — OpenAI tokens/USD on those traces in Langfuse. Not in the local summary.
- [ ] **Consistency** — 10 gold rows × 3 runs; same `question` should keep the same NCM.
- [x] **Langfuse** — `CallbackHandler` on gold `invoke`; `create_score` for `hit2/4/6/8` + `wall_s`; tags `gold` / `v1` / `{tag}`. Custom dashboard **NCM v1 gold** (avg hit8, hierarchy, wall). Do not add LangSmith.
- [x] **HTTP API** — v0: FastAPI `GET /health` + `POST /run` wraps the same `invoke` (`api/main.py`). Curl body: `api/examples/caldera.json`. Auth, CORS, chat, and queue are later.
- [ ] **Deploy the office** — Railway (Docker + GitHub). Image: `Dockerfile`. Do not put `.env` in the image; set `OPENAI_API_KEY`, `TAVILY_API_KEY`, Langfuse keys on the host. AIA dumps stay local (gitignored); prod uses catalog AEC until those dumps are mounted.

- [ ] **OpenTelemetry** — on that API edge (request rate / errors / duration). Propagate `trace_id` into Langfuse. Do not instrument OTel on in-process gold invokes.



## Chat and product API

The office (`POST /run`) stays one-shot. These belong to the conversational layer, not the NCM walk.

- [ ] **Guardrails** — constrain what the chat and `/run` accept and emit (scope: import-cost / NCM only; refuse jailbreaks and off-topic; do not treat the report as a filing; validate CIF / slots before calling the office).
- [ ] **Memory and context** — keep turn history and collected slots (product, CIF, origin, province, tax status) across the conversation so a follow-up does not start from zero; decide what is session memory vs what is re-sent into `question` for `/run`.
