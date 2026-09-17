# TODO — IMPOAI

Done: 97-chapter NCM catalog (JSON, not RAG). Office: NCM first, then hab ∥ price ∥ duty → join → report. DIE from the AIA dump; CIF and origin in the question; CNCE measures (antidumping ad valorem).

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
- [x] Wire the office: NCM → then hab ∥ price ∥ duty → join → report. Hab does not search generic `.gob.ar`: needs a keyword or chapter organism (01–05 SENASA, 30 ANMAT).
- [x] Filter items whose numeric threshold (e.g. 20 t/h vs over 45 t/h) contradicts the question; the grader also rejects without an LLM
- [x] Hab: drop used-goods / C.I.B.U.I.H. hits unless the question asks for used
- [x] Hab: drop SENASA / ANMAT / ANMaC if the product is not that organism
- [ ] Test 3 products outside chapters 1 and 9 (live ibuprofen / tricycle runs happened; no fixed test)



## What a broker uses and we still lack

- [ ] **Technical spec sheet** — ask for / build composition, use, presentation, assembled or not. Do not classify from the trade name alone
- [x] **NESH** — closed: the WCO book is not free; no NESH index in the repo
- [ ] **AFIP/ARCA classification rulings** — **very low priority (post-MVP)**. They cover edge cases, not the general flow. If done, they go after `get_ncm` as validation (not as the classifier). Needs a dump of RG annexes (ARCA library); the AIA nomenclator is not this.
- [ ] If the product could go to two chapters, compare headings with RGI 3 (more specific / essential character / last number) instead of locking the first chapter. **After the spec sheet** (without composition/use, grader retry is enough). Not the next box.



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

- [ ] Customs-broker fees (estimate; % of CIF or flat)
- [ ] Bonded warehouse / terminal / inland freight / local insurance
- [ ] **Habilitations (SENASA/ANMAT, etc.)** — the hab node lists procedures, not amounts. Do not cost them as a % of CIF. Options: user-entered fee; organism → tariff table; Tavily + extract (later)



### Local price / FX (already started)

- [x] **USD/ARS rate** — BCRA Comunicación A 3500 (`api.bcra.gob.ar/estadisticascambiarias`, `tipoCotizacion` USD). Only converts shelf ARS→USD. If the API fails, `USD_ARS_RATE` 1535 and the report says so.
- [ ] Compare **CIF + estimated liquidation** against `precio_ref` (local sale in USD)
