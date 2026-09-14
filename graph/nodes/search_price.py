from langchain_tavily import TavilySearch

from graph.chains.price import price_chain
from graph.state import GraphState

tavily = None


def _tavily():
    global tavily
    if tavily is None:
        tavily = TavilySearch(max_results=5)
    return tavily


def search_price(state: GraphState) -> dict:
    query = f"FOB unit price {state['ncm_descripcion']}"
    raw = _tavily().invoke({"query": query})
    hits = raw.get("results") or []
    hits_text = "\n".join(
        f"- {h.get('title')}: {h.get('content')}" for h in hits if h.get("content")
    )
    quote = price_chain.invoke(
        {
            "question": state["question"],
            "card": f"{state['ncm']} | {state['ncm_descripcion']}",
            "hits": hits_text or "(no hits)",
        }
    )
    print("PRICE", quote.price, quote.currency, "-", quote.motive)
    return {"precio_ref": quote.price, "ncm_currency": quote.currency}
