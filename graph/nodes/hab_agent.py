from typing import Any, Dict
from graph.chains.hab_agent import analista_hab_chain, format_hab_sources
from graph.state import GraphState

def hab_agent(state: GraphState) -> Dict[str, Any]:
    print("Analizando habilitaciones...")
    question = state["question"]
    docs = state.get("hab_docs", [])

    if not docs:
        return {"hab_info": "No hay fuentes de habilitaciones."}
    
    analisis = analista_hab_chain.invoke(
        {"question": question, "sources": format_hab_sources(docs)}
    )

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