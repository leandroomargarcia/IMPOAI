from langchain_core.documents import Document
from langchain_tavily import TavilySearch

from graph.nodes.tavily_hits import tavily_hits
from graph.state import GraphState

tavily = None


def _tavily():
    global tavily
    if tavily is None:
        tavily = TavilySearch(max_results=5)
    return tavily


def web_search_hab(state: GraphState) -> dict:
    print("------WEB SEARCH HAB------")
    question = state["question"]
    query = (
        f"habilitaciones requisitos importación Argentina ANMAT SENASA {question}"
    )
    raw = _tavily().invoke({"query": query})
    hab_docs = [
        Document(
            page_content=hit.get("content") or "",
            metadata={"url": hit.get("url") or "", "title": hit.get("title") or ""},
        )
        for hit in tavily_hits(raw)
        if isinstance(hit, dict) and hit.get("content")
    ]
    return {"hab_docs": hab_docs}