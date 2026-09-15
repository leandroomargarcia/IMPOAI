from typing import Any, Dict
from graph.chains.hab_agent import analista_hab_chain, format_hab_sources
from graph.nodes.calculate_costs import strip_fob_clause
from graph.nodes.web_search_hab import _NO_HAB_MSG, is_official_hab_url
from graph.state import GraphState

def hab_agent(state: GraphState) -> Dict[str, Any]:
    print("Analizando habilitaciones...")
    question = strip_fob_clause(state.get("question") or "")
    docs = [
        doc
        for doc in (state.get("hab_docs") or [])
        if is_official_hab_url((doc.metadata or {}).get("url") or "")
    ]

    if not docs:
        return {"hab_info": _NO_HAB_MSG}
    
    analisis = analista_hab_chain.invoke(
        {"question": question, "sources": format_hab_sources(docs)}
    )

    if not analisis.requisitos:
        return {
            "hab_info": analisis.resumen or _NO_HAB_MSG
        }

    url_by_id = {
        i: (doc.metadata or {}).get("url") or ""
        for i, doc in enumerate(docs or [], start=1)
    }

    lineas = []
    for req in analisis.requisitos:
        urls = []
        for sid in req.source_ids:
            url = url_by_id.get(sid)
            if url:
                urls.append(url)
        cites = " ".join(urls) if urls else "(fuente no encontrada)"
        lineas.append(f"- {req.texto}\n {cites}")

    hab_info = analisis.resumen + "\n\n" + "\n".join(lineas)
    return {"hab_info": hab_info}