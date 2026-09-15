from urllib.parse import urlparse

from langchain_core.documents import Document
from langchain_tavily import TavilySearch

from graph.nodes.calculate_costs import strip_fob_clause
from graph.nodes.tavily_hits import tavily_hits
from graph.state import GraphState

tavily = None
_NO_HAB_MSG = "No se encontraron requisitos específicos de importación en fuentes oficiales."
_OFFICIAL_SUFFIXES = (".gob.ar", ".gov.ar", ".mercosur.int")


def is_official_hab_url(url: str) -> bool:
    host = urlparse(url or "").netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return any(host == s[1:] or host.endswith(s) for s in _OFFICIAL_SUFFIXES)


def _tavily():
    global tavily
    if tavily is None:
        tavily = TavilySearch(max_results=5)
    return tavily


def web_search_hab(state: GraphState) -> dict:
    print("------WEB SEARCH HAB------")
    product = strip_fob_clause(state.get("question") or "")
    query = f"requisitos importación Argentina {product} site:.gob.ar"
    print("HAB query", query)
    raw = _tavily().invoke({"query": query})
    hits = [
        hit
        for hit in tavily_hits(raw)
        if isinstance(hit, dict) and hit.get("content")
    ]
    official = [hit for hit in hits if is_official_hab_url(hit.get("url") or "")]
    dropped = len(hits) - len(official)
    print("HAB hits", len(official), "dropped shops", dropped)
    hab_docs = [
        Document(
            page_content=hit.get("content") or "",
            metadata={"url": hit.get("url") or "", "title": hit.get("title") or ""},
        )
        for hit in official
    ]
    return {"hab_docs": hab_docs}