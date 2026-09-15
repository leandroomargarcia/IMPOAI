from langchain_tavily import TavilySearch

from graph.chains.price import price_chain
from graph.consts import USD_ARS_RATE
from graph.nodes.calculate_costs import strip_fob_clause
from graph.nodes.tavily_hits import tavily_hits
from graph.state import GraphState

tavily = None


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
    usd, currency = _to_usd(quote.price, quote.currency)
    if not usd:
        info = "No se encontró este producto a la venta en Argentina."
        print("PRICE", info)
        return {"precio_ref": 0.0, "ncm_currency": "USD", "precio_info": info}
    if currency == "USD" and (quote.currency or "").upper() in {"ARS", "PESO", "PESOS"}:
        print("PRICE USD", usd, f"(ARS/{USD_ARS_RATE:g} fixed)")
        info = f"{usd:g} USD (ARS/{USD_ARS_RATE:g})"
    else:
        info = f"{usd:g} {currency}"
    return {"precio_ref": usd, "ncm_currency": currency, "precio_info": info}


def _to_usd(amount: float, currency: str, rate: float = USD_ARS_RATE) -> tuple[float, str]:
    if not amount:
        return 0.0, "USD"
    code = (currency or "").upper().replace("$", "ARS")
    if code in {"ARS", "PESO", "PESOS", "AR$"}:
        return amount / rate, "USD"
    return amount, code or "USD"
