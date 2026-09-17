# IMPOAI

LangGraph assistant for Mercosur NCM classification, a first-pass Argentina import-cost estimate, local shelf-price hints, and official import-permit research.

This is a **budgeting tool**, not a customs filing. It does not replace a *despachante* or AFIP / SIM / María.

## Architecture

The NCM walk is serial (chapter → notes → heading → 6-digit subheading if needed → item → card → grade, up to 3 retries). **Selling-price search starts at `START`** (only the `question`; it does not wait for the NCM). After `ncm_done`, habilitation search and CIF liquidation run in parallel. One join waits for price + hab + duty, then the report.

If the grade is not grounded and retries remain, NCM returns to the chapter. Hab and DIE still wait for `ncm_done` (chapter / AEC). Price does not read hab or duty.

![LangGraph: NCM first, then hab, price, and duty in parallel, join, and report](docs/architecture.png)

The `ncm_done` node (not drawn in the Studio export) merges “classified” and “failed” before hab and duty. Price is already running from `START`.

## What it does today

The question carries the product and the **CIF**. Optional: origin, quantity, VAT status, and province.

Example:

```
Caldera acuotubular de vapor 20 toneladas por hora CIF 80000 USD origen China provincia CABA
```

`responsable inscripto` must be stated; otherwise the importer is assumed **monotributista**.

### 1. NCM

Walks the JSON catalog (`ncm/data/catalog.json`, 97 chapters), not PDF RAG. Up to 3 retries.

- If the heading is long, it picks a 6-digit subheading first.
- Drops items whose numeric threshold contradicts the question (e.g. 20 t/h vs “superior a 45 t/h”) without calling the LLM.
- Current DIE comes from the AIA dump (`docs/nomenclador_*.txt`) when present; otherwise the catalog AEC.
- `BK` / `BIT` flags travel in state (legend + 10.5 % VAT).

### 2. Habilitations (parallel)

Tavily runs only if an organism is known: product keywords or NCM chapter (01–05 SENASA, 30 ANMAT). No generic `argentina.gob.ar` search.

Drops shops, used-goods / C.I.B.U.I.H. hits (unless the question asks for used), and URLs from the wrong organism. Lists procedures, not fees.

### 3. Argentine price (parallel)

Looks up a local selling price from the Spanish NCM text. ARS quotes convert to USD with the BCRA **A 3500** wholesale rate. If the API is down, it uses `USD_ARS_RATE` (1535) and the report says so. That figure is a shelf price, not 1:1 comparable to CIF.

### 4. Liquidation (parallel, arithmetic + tables, no LLM)

Duty base = **CIF** from the question (not derived from FOB).

| Line | How |
|---|---|
| DIE | `CIF × DIE%` |
| Statistical fee | 3 % of CIF (Decreto 1140/2024), with USD caps; 0 if origin is Mercosur |
| CNCE measures | Antidumping ad valorem if origin is given; specific × quantity if there is a single rate |
| VAT (IVA) | 21 % default on CIF + DIE + statistical fee + measures. **10.5 %** if the NCM is BK/BIT (productive-use assumption). Override: `IVA 10.5` / `IVA 21` / `IVA exento` |
| VAT perception | RG 2937/4461: 20 % or 10 %, same base. 0 if VAT-exempt |
| Income-tax perception | RG 2281: **11 %** monotributista, 6 % `responsable inscripto`, 3 % `responsable inscripto CVDI` |
| IIBB | 0 if no province. With `provincia CABA` (etc.) uses an estimated general SIRPEI rate. Override: `IIBB 3.5` |

The line-by-line breakdown is `costos_asociados`; the total is `impuestos_estimados`. Min FOB and ambiguous CNCE rates are reported, not liquidated.

### 5. Report

`reporte_final` joins NCM, CIF, origin, province, tax status, duties, reference price, and habilitations. It labels the output as an estimate and warns that broker fees, warehouse/terminal, inland freight, local insurance, and permit tariffs are not included.

## Setup

Python ≥ 3.11.

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
pip install pytest
copy .env.example .env
```

Fill `OPENAI_API_KEY` and `TAVILY_API_KEY` in `.env`. Never commit `.env`.

The catalog is already generated. To rebuild it (Mercosur PDF next to the repo root):

```powershell
.\.venv\Scripts\python.exe -m ncm
```

Local dumps (gitignored) used at lookup time if present:

- `docs/nomenclador_*.txt` and `docs/capitulo_*.txt` — Arancel Integrado (DIE)
- `docs/*medidas*.xlsx` — CNCE measures

## Run

```powershell
.\.venv\Scripts\python.exe -m graph.graph
```

The play-button question lives in `graph/graph.py` (`if __name__ == "__main__"`). Later this will come from a chat turn.

```powershell
.\.venv\Scripts\python.exe -m pytest graph\tests ncm\tests -q
```

Branch tests mock Tavily and the LLM. A full `graph.graph` run hits live APIs (OpenAI, Tavily, BCRA).

## Layout

| Path | Role |
|---|---|
| `ncm/` | Offline PDF parser, catalog, AIA overlay, numeric thresholds |
| `ncm/data/catalog.json` | Full 97-chapter NCM (`python -m ncm`) |
| `ncm/thresholds.py` | Filter 20 t/h vs “superior a 45 t/h” (no LLM) |
| `graph/graph.py` | LangGraph wiring |
| `graph/state.py` | Shared state |
| `graph/consts.py` | Retry budget, VAT, perceptions, IIBB, FX fallback |
| `graph/chains/` | LLM forms (NCM, price, hab) |
| `graph/nodes/` | Nodes: NCM, hab, price, `calc_duty`, join, report |
| `docs/architecture.png` | LangGraph Studio export |
| `docs/observability.md` | Gold set, hierarchical accuracy, traces; HTTP OTel after the API |
| `TODO.md` | Remaining work |

## Status

Still missing: technical spec sheet before classification; food/medicine 10.5 % VAT table (BK/BIT + override only); CIF + liquidation vs shelf price; AFIP rulings and RGI 3 (post-MVP / after the spec sheet); chat to collect CIF and province (they live in `question` today); fixed tests for 3 products outside chapters 1 and 9.
