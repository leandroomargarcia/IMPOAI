# IMPOAI

LangGraph assistant for Mercosur NCM classification, a first-pass import cost estimate, Argentine selling-price hints, and Argentina import-permit research.

This is a **budgeting tool**, not a customs filing. It does not replace a *despachante* or AFIP.

## Architecture

Target graph: NCM walk and habilitation search run **in parallel**, join, then Argentine selling price, costs, and a report. The POC in `graph/graph.py` is still a **single sequence** (classify → AEC on FOB → price → hab).

![Target LangGraph: parallel NCM walk and habilitation search, join, then price, costs, and report](docs/architecture.png)

## What it does today

Given a product description and a **FOB value you type in**:

1. Walk the NCM catalog (chapter → notes → heading → item → code exists → grade), with up to 3 retries
2. Estimate **AEC duty** as `FOB × AEC%` (CIF, statistical fee, VAT, perceptions, IIBB are not in the calculator yet — see `TODO.md`)
3. Search an Argentine **selling price** (Spanish NCM text), convert ARS→USD with a **fixed** FX in `graph/consts.py`
4. Web-search habilitation requirements (SENASA / ANMAT, etc.)

Classification uses a **parsed JSON catalog**, not PDF RAG. The POC catalog covers **chapters 1 and 9** only (coffee, horses, yerba mate, …).

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

Edit the play button in `graph/graph.py`: `question` + `fob`. Later this will come from a chat turn.

```powershell
.\.venv\Scripts\python.exe -m pytest graph\tests ncm\tests -q
```

Branch tests mock Tavily and the LLM. A full `graph.graph` run hits live APIs.

## Layout

| Path | Role |
|---|---|
| `ncm/` | PDF parser (offline) + catalog lookup |
| `graph/graph.py` | LangGraph wiring |
| `graph/chains/` | LLM forms (NCM, price, hab) |
| `graph/nodes/` | State in / state out |
| `docs/architecture.png` | Target graph (LangGraph Studio export) |
| `TODO.md` | Full catalog, broker-style liquidation, FX scrape |

## Status

POC. Next: complete NCM catalog, CIF-based tax stack, live USD/ARS, conversational input for FOB / freight / province.
