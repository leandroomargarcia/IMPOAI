# IMPOAI

LangGraph assistant for Mercosur NCM classification, a first-pass import cost estimate, Argentine selling-price hints, and Argentina import-permit research.

This is a **budgeting tool**, not a customs filing. It does not replace a *despachante* or AFIP.

## Architecture

Target graph: NCM walk and habilitation search run **in parallel**, join, then Argentine selling price, AEC on FOB, and a written report. Duty is still `FOB × AEC%` (not a CIF liquidation).

![Target LangGraph: parallel NCM walk and habilitation search, join, then price, costs, and report](docs/architecture.png)

## What it does today

Given a product description and a **FOB in the same question** (e.g. `green coffee beans FOB 4.50`):

1. Walk the NCM catalog (chapter → notes → heading → 6-digit subheading if the heading is long → item → code exists → grade), with up to 3 retries, **in parallel** with habilitation search
2. Estimate **AEC duty** as `FOB × AEC%` (CIF, statistical fee, VAT, perceptions, IIBB are not in the calculator yet — see `TODO.md`)
3. Search an Argentine **selling price** (Spanish NCM text), convert ARS→USD with a **fixed** FX in `graph/consts.py`
5. Assemble a **report** (`reporte_final`) that labels the output as an estimate, not an AFIP filing

Classification uses a **parsed JSON catalog**, not PDF RAG. The catalog covers **all 97 NCM chapters** (`ncm/data/catalog.json`). Rebuild it offline with `python -m ncm` (needs the Mercosur PDF next to the repo root).

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
```

Fill `OPENAI_API_KEY` and `TAVILY_API_KEY` in `.env`. Never commit `.env`.

## Run

```powershell
.\.venv\Scripts\python.exe -m graph.graph
```

Edit the play button in `graph/graph.py`: put the product and the FOB in `question` (e.g. `green coffee beans FOB 4.50`). Later this will come from a chat turn.

```powershell
.\.venv\Scripts\python.exe -m pytest graph\tests ncm\tests -q
```

Branch tests mock Tavily and the LLM. A full `graph.graph` run hits live APIs.

## Layout

| Path | Role |
|---|---|
| `ncm/` | PDF parser (offline) + catalog lookup |
| `ncm/data/catalog.json` | Full 97-chapter NCM (rebuild: `python -m ncm`) |
| `graph/graph.py` | LangGraph wiring |
| `graph/chains/` | LLM forms (NCM, price, hab) |
| `graph/nodes/` | State in / state out |
| `docs/architecture.png` | Target graph (LangGraph Studio export) |
| `TODO.md` | Full catalog, broker-style liquidation, FX scrape |

## Status

POC graph matches the office diagram (parallel NCM + hab → join → price → AEC stub → report). Next: CIF-based tax stack, live USD/ARS, conversational input for FOB / freight / province, then observability.
