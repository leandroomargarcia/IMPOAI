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
_ANMAT_CHAPTERS = frozenset({"30"})
_SENASA_CHAPTERS = frozenset(f"{n:02d}" for n in range(1, 6))
_USED_QUESTION_RE = (
    "usado",
    "usada",
    "usados",
    "usadas",
    "used",
    "secondhand",
)
_USED_REGIME_MARKERS = (
    "bienesusados",
    "hidrocarburifer",
    "cibuih",
)
_ANMAT_KEYS = (
    "anmat",
    "medicament",
    "ibuprofen",
    "farmac",
    "comprimido",
    "vacuna",
    "especialidadmedicinal",
)
_SENASA_KEYS = (
    "senasa",
    "animal",
    "caballo",
    "equino",
    "horse",
    "carne",
    "alimento",
    "ganado",
)
_ANMAC_KEYS = (
    "anmac",
    "armas",
    "municion",
    "explosivo",
    "materialescontrolad",
)
_HAB_DOMAIN_KEYWORDS = (
    (("anmat.gob.ar",), _ANMAT_KEYS),
    (("senasa.gob.ar",), _SENASA_KEYS),
)


def _chapter(chapter: str | None) -> str:
    raw = (chapter or "").strip()
    return raw.zfill(2) if raw else ""


def hab_domains(question: str, chapter: str | None = None) -> list[str]:
    """Tavily include_domains from product keywords and, after NCM, the chapter."""
    blob = fold(question).replace(" ", "")
    found: list[str] = []
    for domains, keys in _HAB_DOMAIN_KEYWORDS:
        if any(key in blob for key in keys):
            found.extend(domains)
    cap = _chapter(chapter)
    if cap in _ANMAT_CHAPTERS:
        found.append("anmat.gob.ar")
    if cap in _SENASA_CHAPTERS:
        found.append("senasa.gob.ar")
    return list(dict.fromkeys(found))


def asks_used_goods(question: str) -> bool:
    blob = fold(question).replace(" ", "")
    return any(key in blob for key in _USED_QUESTION_RE)


def is_used_regime_hit(hit: dict) -> bool:
    blob = fold(f"{hit.get('url') or ''} {hit.get('title') or ''}").replace(" ", "").replace("-", "")
    return any(marker in blob for marker in _USED_REGIME_MARKERS)


def _hit_blob(hit: dict) -> str:
    return fold(f"{hit.get('url') or ''} {hit.get('title') or ''}").replace(" ", "").replace("-", "")


def is_wrong_organism_hit(
    question: str, hit: dict, chapter: str | None = None
) -> bool:
    """True if the URL is SENASA/ANMAT/ANMaC and neither the product nor the NCM chapter match."""
    qblob = fold(question).replace(" ", "")
    cap = _chapter(chapter)
    allow_anmat = cap in _ANMAT_CHAPTERS or any(key in qblob for key in _ANMAT_KEYS)
    allow_senasa = cap in _SENASA_CHAPTERS or any(key in qblob for key in _SENASA_KEYS)
    allow_anmac = any(key in qblob for key in _ANMAC_KEYS)
    hblob = _hit_blob(hit)
    if "anmat" in hblob and not allow_anmat:
        return True
    if "senasa" in hblob and not allow_senasa:
        return True
    if any(marker in hblob for marker in ("anmac", "materialescontrolad", "autorizaciondeimportacion")) and not allow_anmac:
        return True
    return False


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


def _official_hits(
    raw,
    question: str = "",
    allow_used: bool = False,
    chapter: str | None = None,
) -> tuple[list, int]:
    hits = [
        hit
        for hit in tavily_hits(raw)
        if isinstance(hit, dict) and hit.get("content")
    ]
    official = [hit for hit in hits if is_official_hab_url(hit.get("url") or "")]
    dropped = [hit.get("url") or "" for hit in hits if hit not in official]
    if dropped:
        print("HAB dropped", dropped)
    if not allow_used:
        kept = []
        dropped_used = []
        for hit in official:
            if is_used_regime_hit(hit):
                dropped_used.append(hit.get("url") or "")
            else:
                kept.append(hit)
        if dropped_used:
            print("HAB dropped used-regime", dropped_used)
        official = kept
    kept = []
    dropped_org = []
    for hit in official:
        if is_wrong_organism_hit(question, hit, chapter):
            dropped_org.append(hit.get("url") or "")
        else:
            kept.append(hit)
    if dropped_org:
        print("HAB dropped organism", dropped_org)
    return kept, len(dropped)


def _short_product(product: str) -> str:
    for token in (product or "").split():
        letters = "".join(c for c in token if c.isalpha())
        if len(letters) >= 4:
            return letters
    return product


def _search(
    query: str,
    include_domains: list[str] | None = None,
    allow_used: bool = False,
    question: str = "",
    chapter: str | None = None,
) -> tuple[list, int]:
    payload: dict = {"query": query}
    if include_domains:
        payload["include_domains"] = include_domains
    try:
        return _official_hits(
            _client(include_domains).invoke(payload),
            question=question,
            allow_used=allow_used,
            chapter=chapter,
        )
    except ToolException:
        print("HAB tavily empty")
        return [], 0


def _hab_query(product: str, question: str) -> str:
    query = f"requisitos importación Argentina {product}".strip()
    if not asks_used_goods(question):
        query = f"{query} bien nuevo"
    return query


def web_search_hab(state: GraphState) -> dict:
    print("------WEB SEARCH HAB------")
    question = state.get("question") or ""
    chapter = state.get("ncm_chapter") or ""
    product = strip_fob_clause(question)
    domains = hab_domains(question, chapter)
    if not domains:
        print("HAB skip no organism", "chapter", chapter or "-")
        return {"hab_docs": []}
    allow_used = asks_used_goods(question)
    query = _hab_query(product, question)
    print("HAB query", query, "domains", ",".join(domains))
    official, dropped = _search(query, domains, allow_used, question, chapter)
    print("HAB hits", len(official), "dropped shops", dropped)
    if not official:
        short = _short_product(product)
        if short and short.lower() != product.lower():
            retry = _hab_query(short, question)
            print("HAB retry", retry, "domains", ",".join(domains))
            official, dropped = _search(retry, domains, allow_used, question, chapter)
            print("HAB hits", len(official), "dropped shops", dropped)
            print("HAB hits", len(official), "dropped shops", dropped)
    hab_docs = [
        Document(
            page_content=hit.get("content") or "",
            metadata={"url": hit.get("url") or "", "title": hit.get("title") or ""},
        )
        for hit in official
    ]
    return {"hab_docs": hab_docs}
