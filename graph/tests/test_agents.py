import graph.nodes.hab_agent as hab_agent_mod
import graph.nodes.ncm_node as ncm_node
import graph.nodes.search_price as search_price_mod
import graph.nodes.web_search_hab as web_search_mod
import pytest
from langgraph.graph import END, START, StateGraph

from graph.nodes.calculate_costs import calc_duty
from graph.nodes.hab_agent import hab_agent
from graph.nodes.ncm_node import (
    after_grade,
    after_heading,
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
            "ok": "calc_duty",
            "retry": "pick_chapter",
            "fail": END,
        }
    )
    g.add_edge("calc_duty", "search_price")
    g.add_edge("search_price", END)
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
    out = _ncm_app().invoke(
        {"question": "purebred breeding horse CIF 1000", "attempts": 0}
    )
    assert out["ncm"] == "0101.21.00" # NCM encontrado
    assert out["ncm_aec"] == 0 # AEC encontrado
    assert out["es_valido"] is True # NCM válido
    assert out["cif"] == 1000.0
    assert out["impuestos_estimados"] == 0.0 # DIE 0% of CIF
    assert out["precio_ref"] == 100.0 # already USD, no FX
    assert out.get("ncm_currency") == "USD"
    assert "No se encontró este producto" not in (out.get("precio_info") or "")
    assert not out.get("hab_docs") # No se encontraron documentos de HAB
    assert not out.get("hab_info") # No se encontraron información de HAB


def test_duty_uses_user_cif_not_sale_price():
    out = calc_duty({"question": "coffee CIF 4.50", "ncm_aec": 10, "precio_ref": 9999})
    assert out["impuestos_estimados"] == pytest.approx(0.45)
    assert out["cif"] == pytest.approx(4.50)


def test_duty_ignores_fob_in_question():
    out = calc_duty({"question": "coffee FOB 4.50", "ncm_aec": 10})
    assert out["impuestos_estimados"] == 0


def test_parse_cif_from_question():
    from graph.nodes.calculate_costs import parse_cif, strip_cif_clause

    assert parse_cif("green coffee beans CIF 4.50") == pytest.approx(4.50)
    assert parse_cif("café cif: 4,50") == pytest.approx(4.50)
    assert parse_cif("green coffee beans") is None
    assert parse_cif("coffee FOB 4.50") is None
    assert "CIF" not in strip_cif_clause("triciclo plegable CIF 223 USD")
    assert "223" not in strip_cif_clause("triciclo plegable CIF 223 USD")


def test_price_query_uses_product_not_ncm_kg():
    from graph.nodes.search_price import _price_query

    q = _price_query(
        {
            "question": "JMMD Triciclo plegable CIF 223 USD",
            "ncm_descripcion": (
                "Triciclos, patinetes, coches de pedal y juguetes similares con ruedas; "
                "coches y sillas de ruedas para muñecas / Triciclos, patinetes"
            ),
        }
    )
    assert "kg" not in q.lower()
    assert "CIF" not in q
    assert "223" not in q
    assert "Triciclo" in q or "triciclo" in q.lower()


def test_duty_skips_without_cif_in_question():
    out = calc_duty({"question": "green coffee beans", "ncm_aec": 10, "cif": 4.50})
    assert out["impuestos_estimados"] == 0


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


def test_official_hab_url():
    from graph.nodes.web_search_hab import is_official_hab_url

    assert is_official_hab_url("https://www.argentina.gob.ar/senasa")
    assert is_official_hab_url("https://ejemplo.gob.ar/senasa")
    assert is_official_hab_url("https://www.mercosur.int/ncm")
    assert not is_official_hab_url("https://es.accio.com/plp/triciclo")
    assert not is_official_hab_url("https://www.mercadolibre.com.ar/triciclo")
    assert not is_official_hab_url("")


def test_hab_drops_shop_hits(monkeypatch):
    monkeypatch.setattr(
        web_search_mod,
        "tavily",
        type("T", (), {
            "invoke": staticmethod(lambda _: {
                "results": [
                    {
                        "title": "Accio",
                        "url": "https://es.accio.com/plp/triciclo-para-adultos-precio-argentina",
                        "content": "Certificación EEC para facilitar la importación.",
                    },
                    {
                        "title": "SENASA",
                        "url": "https://www.argentina.gob.ar/senasa",
                        "content": "Importación de equinos requiere certificado zoosanitario SENASA.",
                    },
                ]
            })
        })(),
    )
    out = web_search_hab({"question": "triciclo plegable CIF 223 USD"})
    urls = [doc.metadata["url"] for doc in out["hab_docs"]]
    assert urls == ["https://www.argentina.gob.ar/senasa"]


def test_hab_shops_only_says_not_found(monkeypatch):
    monkeypatch.setattr(
        web_search_mod,
        "tavily",
        type("T", (), {
            "invoke": staticmethod(lambda _: {
                "results": [{
                    "title": "Accio",
                    "url": "https://es.accio.com/plp/triciclo",
                    "content": "Certificación EEC para facilitar la importación.",
                }]
            })
        })(),
    )
    called = []

    def _invoke(_):
        called.append(1)
        raise AssertionError("hab LLM must not run on shop hits")

    monkeypatch.setattr(
        hab_agent_mod,
        "analista_hab_chain",
        type("C", (), {"invoke": staticmethod(_invoke)})(),
    )
    out = _hab_app().invoke({"question": "triciclo plegable"})
    assert out.get("hab_docs") == []
    assert called == []
    assert "No se encontraron requisitos específicos de importación" in out["hab_info"]
    assert "EEC" not in out["hab_info"]


def test_tavily_hits_json_string_and_answer():
    from graph.nodes.tavily_hits import tavily_hits

    raw = '{"answer": "2 USD/kg", "results": [{"title": "A", "content": "cafe"}]}'
    hits = tavily_hits(raw)
    assert hits[0]["content"] == "2 USD/kg"
    assert hits[1]["title"] == "A"


def test_tavily_hits_keeps_plain_text_for_price():
    from graph.nodes.tavily_hits import tavily_hits

    assert tavily_hits("not json", keep_raw_text=True)[0]["content"] == "not json"
    assert tavily_hits("not json") == []


def test_ars_to_usd_fixed_rate():
    from graph.consts import USD_ARS_RATE
    from graph.nodes.search_price import _to_usd

    usd, code = _to_usd(USD_ARS_RATE * 10.0, "ARS")
    assert code == "USD"
    assert usd == pytest.approx(10.0)
    usd2, code2 = _to_usd(8.0, "USD")
    assert code2 == "USD"
    assert usd2 == pytest.approx(8.0)


def test_missing_argentine_price_is_explained(monkeypatch):
    monkeypatch.setattr(
        search_price_mod,
        "tavily",
        type("T", (), {"invoke": staticmethod(lambda _: {"results": [{"title": "t", "content": "sin listados"}]})})(),
    )
    monkeypatch.setattr(
        search_price_mod,
        "price_chain",
        type("C", (), {"invoke": staticmethod(lambda _: type("R", (), {"price": 0.0, "currency": "ARS", "motive": "no"})())})(),
    )
    out = search_price({"question": "JMMD triciclo", "ncm": "9503.00.10", "ncm_descripcion": "x"})
    assert out["precio_ref"] == 0.0
    assert "No se encontró este producto a la venta en Argentina" in out["precio_info"]
    from graph.nodes.orchestrator import orchestrator

    report = orchestrator({**out, "question": "JMMD triciclo"})["reporte_final"]
    assert "No se encontró este producto a la venta en Argentina" in report
    assert "0.0 USD" not in report.split("Habilitaciones")[0]


def _fake_choice(**fields):
    return type("R", (), fields)()


def _patch_office(monkeypatch, *, item="0101.21.00", valid=True):
    monkeypatch.setattr(
        ncm_node,
        "router",
        type("C", (), {"invoke": staticmethod(lambda _: _fake_choice(chapter="01", motive="x"))})(),
    )
    monkeypatch.setattr(
        ncm_node,
        "heading_chain",
        type("C", (), {"invoke": staticmethod(lambda _: _fake_choice(heading="01.01", motive="x"))})(),
    )
    monkeypatch.setattr(
        ncm_node,
        "item_chain",
        type("C", (), {"invoke": staticmethod(lambda _: _fake_choice(item=item, motive="x"))})(),
    )
    monkeypatch.setattr(
        ncm_node,
        "grade_chain",
        type("C", (), {"invoke": staticmethod(lambda _: _fake_choice(is_valid=valid, motive="ok" if valid else "no"))})(),
    )
    monkeypatch.setattr(
        search_price_mod,
        "tavily",
        type("T", (), {"invoke": staticmethod(lambda _: {"results": [{"title": "t", "content": "USD 100"}]})})(),
    )
    monkeypatch.setattr(
        search_price_mod,
        "price_chain",
        type("C", (), {"invoke": staticmethod(lambda _: _fake_choice(price=100.0, currency="USD", motive="x"))})(),
    )
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


def test_office_parallel_join_writes_report(monkeypatch):
    from graph.graph import build_graph

    _patch_office(monkeypatch)
    out = build_graph().invoke(
        {"question": "purebred breeding horse CIF 1000", "attempts": 0}
    )
    assert out["ncm"] == "0101.21.00"
    assert out["es_valido"] is True
    assert out["impuestos_estimados"] == 0.0
    assert out["precio_ref"] == 100.0
    assert "SENASA" in out["hab_info"]
    assert "0101.21.00" in out["reporte_final"]
    assert "No se encontró este producto" not in out["reporte_final"]
    assert "estimación" in out["reporte_final"].lower()
    assert "no es un despacho" in out["reporte_final"].lower()


def test_ncm_fail_still_joins_hab_and_report(monkeypatch):
    from graph.graph import build_graph

    _patch_office(monkeypatch, valid=False)
    out = build_graph().invoke(
        {"question": "purebred breeding horse CIF 1000", "attempts": 0}
    )
    assert out["es_valido"] is False
    assert "No se pudo clasificar" in out["ncm_info"]
    assert "SENASA" in out["hab_info"]
    assert out["reporte_final"]
    assert out["attempts"] == 3


def test_missing_ncm_skips_grader(monkeypatch):
    from graph.graph import build_graph

    called = []

    def _grade(_):
        called.append(1)
        return _fake_choice(is_valid=True, motive="ok")

    _patch_office(monkeypatch, item="9999.99.99")
    monkeypatch.setattr(ncm_node, "grade_chain", type("C", (), {"invoke": staticmethod(_grade)})())
    out = build_graph().invoke(
        {"question": "purebred breeding horse CIF 10", "attempts": 0}
    )
    assert called == []
    assert out["es_valido"] is False
    assert "No se pudo clasificar" in out["ncm_info"]


def test_after_heading_uses_subheading_when_list_is_long(monkeypatch):
    monkeypatch.setattr(
        ncm_node.catalog,
        "list_items",
        lambda _: [{"ncm": f"0901.11.{i:02d}"} for i in range(21)],
    )
    monkeypatch.setattr(
        ncm_node.catalog,
        "list_subheadings",
        lambda _: [{"subheading": "0901.11", "description": "x"}],
    )
    assert after_heading({"ncm_heading": "09.01"}) == "subheading"
    monkeypatch.setattr(ncm_node.catalog, "list_items", lambda _: [{"ncm": "0901.11.10"}])
    assert after_heading({"ncm_heading": "09.01"}) == "item"


def test_grade_prompt_treats_notes_as_exclusions():
    from graph.chains.ncm_agent import GRADE_SYSTEM

    text = GRADE_SYSTEM.lower()
    assert "exclusion" in text
    assert "do not reject because the product name is absent" in text
    assert "false if the notes exclude it or the description does not match" not in text



