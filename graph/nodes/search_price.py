import json
import uuid
import urllib.error
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor

from langchain_tavily import TavilySearch

from graph.chains.price import price_chain
from graph.consts import BCRA_USD_URL, USD_ARS_RATE
from graph.nodes.calculate_costs import strip_fob_clause
from graph.nodes.tavily_hits import tavily_hits
from graph.state import GraphState

_ARS = {"ARS", "PESO", "PESOS", "AR$"}

tavily = None
_jobs: dict[str, Future] = {}
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="impoai-price")


def _tavily():
    global tavily
    if tavily is None:
        tavily = TavilySearch(
            max_results=5,
            country="argentina",
            include_answer=True,
        )
    return tavily


def _price_query(state: GraphState) -> str:
    name = strip_fob_clause(state.get("question") or "")
    path = state.get("ncm_descripcion") or ""
    short = path.split("/")[-1].strip() if path else ""
    if short and 3 < len(short) <= 80 and short.lower() not in name.lower():
        name = f"{name} {short}".strip()
    return f"precio Argentina {name}".strip()


def search_price(state: GraphState) -> dict:
    query = _price_query(state)
    print("PRICE query", query)
    raw = _tavily().invoke({"query": query})
    hits = tavily_hits(raw, keep_raw_text=True)
    print("PRICE hits", len(hits))
    hits_text = "\n".join(
        f"- {h.get('title')}: {h.get('content')}"
        for h in hits
        if isinstance(h, dict) and h.get("content")
    )
    quote = price_chain.invoke(
        {
            "question": state["question"],
            "card": f"{state.get('ncm') or '-'} | {state.get('ncm_descripcion') or state.get('question')}",
            "hits": hits_text or "(no hits)",
        }
    )
    print("PRICE", quote.price, quote.currency, "-", quote.motive)
    code = (quote.currency or "").upper().replace("$", "ARS")
    rate, fx_note = (USD_ARS_RATE, "fijo")
    if code in _ARS:
        rate, fx_note = fetch_usd_ars_rate()
    usd, currency = _to_usd(quote.price, quote.currency, rate)
    if not usd:
        info = "No se encontró este producto a la venta en Argentina."
        print("PRICE", info)
        return {"precio_ref": 0.0, "ncm_currency": "USD", "precio_info": info}
    if currency == "USD" and code in _ARS:
        print("PRICE USD", usd, f"(ARS/{rate:g} {fx_note})")
        info = f"{usd:g} USD (ARS/{rate:g} {fx_note})"
    else:
        info = f"{usd:g} {currency}"
    return {"precio_ref": usd, "ncm_currency": currency, "precio_info": info}


def search_price_start(state: GraphState) -> dict:
    """Kick Tavily in a thread so LangGraph does not wait before load_notes."""
    job_id = str(uuid.uuid4())
    snapshot = {
        "question": state.get("question") or "",
        "ncm": state.get("ncm") or "",
        "ncm_descripcion": state.get("ncm_descripcion") or "",
    }
    _jobs[job_id] = _pool.submit(search_price, snapshot)
    print("PRICE start", job_id)
    return {"price_job_id": job_id}


def search_price_wait(state: GraphState) -> dict:
    job_id = state.get("price_job_id") or ""
    fut = _jobs.pop(job_id, None)
    if fut is None:
        print("PRICE wait missing job")
        return {
            "precio_ref": 0.0,
            "ncm_currency": "USD",
            "precio_info": "No se encontró este producto a la venta en Argentina.",
        }
    print("PRICE wait", job_id)
    return fut.result()


def parse_bcra_usd(payload: dict) -> tuple[float, str] | None:
    for row in payload.get("results") or []:
        fecha = str(row.get("fecha") or "")
        for det in row.get("detalle") or []:
            if str(det.get("codigoMoneda") or "").upper() != "USD":
                continue
            rate = float(det.get("tipoCotizacion") or 0)
            if rate > 0:
                return rate, fecha
    return None


def fetch_usd_ars_rate() -> tuple[float, str]:
    """BCRA Comunicación A 3500 (mayorista). Fallback: USD_ARS_RATE."""
    try:
        req = urllib.request.Request(
            BCRA_USD_URL,
            headers={"User-Agent": "IMPOAI/1.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        parsed = parse_bcra_usd(data)
        if parsed:
            rate, fecha = parsed
            print("FX BCRA A3500", rate, fecha)
            return rate, f"BCRA A3500 {fecha}"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, OSError) as exc:
        print("FX BCRA fail", exc)
    return USD_ARS_RATE, "fijo (BCRA no disponible)"


def _to_usd(amount: float, currency: str, rate: float = USD_ARS_RATE) -> tuple[float, str]:
    if not amount:
        return 0.0, "USD"
    code = (currency or "").upper().replace("$", "ARS")
    if code in _ARS:
        return amount / rate, "USD"
    return amount, code or "USD"
