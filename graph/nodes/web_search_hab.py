from urllib.parse import urlparse

from langchain_core.documents import Document
from langchain_core.tools import ToolException
from langchain_tavily import TavilySearch

from graph.nodes.calculate_costs import strip_fob_clause
from graph.nodes.tavily_hits import tavily_hits
from graph.state import GraphState
from ncm.medidas import fold

tavily = None
_NO_HAB_MSG = "No se encontraron requisitos específicos de importación en fuentes oficiales."
_OFFICIAL_SUFFIXES = (".gob.ar", ".gov.ar", ".mercosur.int")
_DEFAULT_HAB_DOMAINS = ("argentina.gob.ar",)
_HAB_DOMAIN_KEYWORDS = (
    (
        ("anmat.gob.ar",),
        (
            "anmat",
            "medicament",
            "ibuprofen",
            "farmac",
            "comprimido",
            "vacuna",
            "especialidadmedicinal",
        ),
    ),
    (
        ("senasa.gob.ar",),
        (
            "senasa",
            "animal",
            "caballo",
            "equino",
            "horse",
            "carne",
            "alimento",
            "ganado",
        ),
    ),
)


def hab_domains(question: str) -> list[str]:
    """Pick Tavily include_domains from the product text (hab runs before NCM)."""
    blob = fold(question).replace(" ", "")
    found: list[str] = []
    for domains, keys in _HAB_DOMAIN_KEYWORDS:
        if any(key in blob for key in keys):
            found.extend(domains)
    if found:
        return list(dict.fromkeys(found))
    return list(_DEFAULT_HAB_DOMAINS)


def is_official_hab_url(url: str) -> bool:
    host = urlparse(url or "").netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return any(host == s[1:] or host.endswith(s) for s in _OFFICIAL_SUFFIXES)


def _client(include_domains: list[str] | None = None):
    """Tests patch module-level `tavily`. Live hab must set domains on the constructor."""
    if tavily is not None:
        return tavily
    kwargs: dict = {"max_results": 5}
    if include_domains:
        kwargs["include_domains"] = include_domains
    return TavilySearch(**kwargs)


def _official_hits(raw) -> tuple[list, int]:
    hits = [
        hit
        for hit in tavily_hits(raw)
        if isinstance(hit, dict) and hit.get("content")
    ]
    official = [hit for hit in hits if is_official_hab_url(hit.get("url") or "")]
    dropped = [hit.get("url") or "" for hit in hits if hit not in official]
    if dropped:
        print("HAB dropped", dropped)
    return official, len(dropped)


def _short_product(product: str) -> str:
    for token in (product or "").split():
        letters = "".join(c for c in token if c.isalpha())
        if len(letters) >= 4:
            return letters
    return product


def _search(query: str, include_domains: list[str] | None = None) -> tuple[list, int]:
    payload: dict = {"query": query}
    if include_domains:
        payload["include_domains"] = include_domains
    try:
        return _official_hits(_client(include_domains).invoke(payload))
    except ToolException:
        print("HAB tavily empty")
        return [], 0


def web_search_hab(state: GraphState) -> dict:
    print("------WEB SEARCH HAB------")
    product = strip_fob_clause(state.get("question") or "")
    domains = hab_domains(state.get("question") or "")
    query = f"requisitos importación Argentina {product}"
    print("HAB query", query, "domains", ",".join(domains))
    official, dropped = _search(query, domains)
    print("HAB hits", len(official), "dropped shops", dropped)
    if not official:
        short = _short_product(product)
        if short and short.lower() != product.lower():
            retry = f"requisitos importación Argentina {short}"
            print("HAB retry", retry, "domains", ",".join(domains))
            official, dropped = _search(retry, domains)
            print("HAB hits", len(official), "dropped shops", dropped)
    hab_docs = [
        Document(
            page_content=hit.get("content") or "",
            metadata={"url": hit.get("url") or "", "title": hit.get("title") or ""},
        )
        for hit in official
    ]
    return {"hab_docs": hab_docs}
