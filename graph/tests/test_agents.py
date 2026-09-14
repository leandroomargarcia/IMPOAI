import graph.nodes.hab_agent as hab_agent_mod
import graph.nodes.ncm_node as ncm_node
import graph.nodes.search_price as search_price_mod
import graph.nodes.web_search_hab as web_search_mod
from langgraph.graph import END, START, StateGraph

from graph.nodes.calculate_costs import calc_duty
from graph.nodes.hab_agent import hab_agent
from graph.nodes.ncm_node import (
    after_grade,
    choose_heading,
    choose_item,
    fetch_ncm,
    grade_ncm,
    load_notes,
    pick_chapter,
)
from graph.nodes.search_price import search_price
from graph.nodes.web_search_hab import web_search_hab
from graph.state import GraphState

def _ncm_app():
    g = StateGraph(GraphState)
    g.add_node("pick_chapter", pick_chapter)
    g.add_node("load_notes", load_notes)
    g.add_node("choose_heading", choose_heading)
    g.add_node("choose_item", choose_item)
    g.add_node("fetch_ncm", fetch_ncm)
    g.add_node("grade_ncm", grade_ncm)
    g.add_node("search_price", search_price)
    g.add_node("calc_duty", calc_duty)
    g.add_edge(START, "pick_chapter")
    g.add_edge("pick_chapter", "load_notes")
    g.add_edge("load_notes", "choose_heading")
    g.add_edge("choose_heading", "choose_item")
    g.add_edge("choose_item", "fetch_ncm")
    g.add_edge("fetch_ncm", "grade_ncm")
    g.add_conditional_edges(
        "grade_ncm",
        after_grade,
        {
            "ok": "search_price",
            "retry": "pick_chapter",
            "fail": END,
        }
    )
    g.add_edge("search_price", "calc_duty")
    g.add_edge("calc_duty", END)
    return g.compile()

def _hab_app():
    g = StateGraph(GraphState)
    g.add_node("web_search_hab", web_search_hab)
    g.add_node("hab_agent", hab_agent)
    g.add_edge(START, "web_search_hab")
    g.add_edge("web_search_hab", "hab_agent")
    g.add_edge("hab_agent", END)
    return g.compile()

def test_rama_ncm_caballo(monkeypatch):
    monkeypatch.setattr(
        ncm_node,
        "router",
        type("C", (), {"invoke": staticmethod(lambda _: type("R", (), {"chapter": "01", "motive": "x"})())})(),
    )
    monkeypatch.setattr(
        ncm_node,
        "heading_chain",
        type("C", (), {"invoke": staticmethod(lambda _: type("R", (), {"heading": "01.01", "motive": "x"})())})(),
    )
    monkeypatch.setattr(
        ncm_node,
        "item_chain",
        type("C", (), {"invoke": staticmethod(lambda _: type("R", (), {"item": "0101.21.00", "motive": "x"})())})(),
    )
    monkeypatch.setattr(
        ncm_node,
        "grade_chain",
        type("C", (), {"invoke": staticmethod(lambda _: type("R", (), {"is_valid": True, "motive": "ok"})())})(),
    )
    monkeypatch.setattr(
        search_price_mod,
        "tavily",
        type("T", (), {"invoke": staticmethod(lambda _: {"results": [{"title": "t", "content": "USD 100"}]})})(),
    )
    monkeypatch.setattr(
        search_price_mod,
        "price_chain",
        type("C", (), {"invoke": staticmethod(lambda _: type("R", (), {"price": 100.0, "currency": "USD", "motive": "x"})())})(),
    )
    out = _ncm_app().invoke({"question": "purebred breeding horse", "attempts": 0})
    assert out["ncm"] == "0101.21.00" # NCM encontrado
    assert out["ncm_aec"] == 0 # AEC encontrado
    assert out["es_valido"] is True # NCM válido
    assert out["precio_ref"] == 100.0 # Precio de referencia encontrado
    assert out["impuestos_estimados"] == 0.0 # Impuestos estimados encontrado
    assert not out.get("hab_docs") # No se encontraron documentos de HAB
    assert not out.get("hab_info") # No se encontraron información de HAB

def test_rama_hab_sin_ncm(monkeypatch):
    monkeypatch.setattr(
        web_search_mod,
        "tavily",
        type("T", (), {
            "invoke": staticmethod(lambda _: {
                "results": [{
                    "title": "SENASA",
                    "url": "https://ejemplo.gob.ar/senasa",
                    "content": "Importación de equinos requiere certificado zoosanitario SENASA.",
                }]
            })
        })(),
    )
    class Fake:
        requisitos = [type("R", (), {"texto": "Certificado SENASA", "source_ids": [1]})()]
        resumen = "Hay un requisito SENASA."
    
    monkeypatch.setattr(
        hab_agent_mod,
        "analista_hab_chain",
        type("C", (), {"invoke": staticmethod(lambda _: Fake())})(),
    )
    
    out = _hab_app().invoke({"question": "purebred breeding horse"})

    assert len(out.get("hab_docs", [])) == 1 # 1 documento encontrado
    assert "SENASA" in out["hab_info"] # Titulo del documento encontrado
    assert "https://ejemplo.gob.ar/senasa" in out["hab_info"] # URL del documento encontrado
    assert not out.get("ncm") # No se encontró NCM
    assert out.get("es_valido") is None

