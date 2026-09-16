import graph.nodes.hab_agent as hab_agent_mod
import graph.nodes.ncm_node as ncm_node
import graph.nodes.search_price as search_price_mod
import graph.nodes.web_search_hab as web_search_mod
import pytest
from langgraph.graph import END, START, StateGraph

from graph.consts import IVA_RATE
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


def _taxes(
    cif: float,
    die: float,
    te: float,
    extra: float = 0.0,
    iva_rate: float = IVA_RATE,
    ganancias_rate: float = 11.0,
    iibb_rate: float = 0.0,
) -> float:
    base = cif + die + te + extra
    iva = base * (iva_rate / 100)
    perc_iva_rate = 0.0 if iva_rate <= 0 else (10.0 if iva_rate <= 10.5 else 20.0)
    perc_iva = base * (perc_iva_rate / 100)
    ganancias = base * (ganancias_rate / 100)
    iibb = base * (iibb_rate / 100)
    return die + te + extra + iva + perc_iva + ganancias + iibb

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
    assert out["impuestos_estimados"] == pytest.approx(_taxes(1000, 0, 30))  # DIE 0 + TE 3% + IVA
    assert out["precio_ref"] == 100.0 # already USD, no FX
    assert out.get("ncm_currency") == "USD"
    assert "No se encontró este producto" not in (out.get("precio_info") or "")
    assert not out.get("hab_docs") # No se encontraron documentos de HAB
    assert not out.get("hab_info") # No se encontraron información de HAB


def test_duty_uses_user_cif_not_sale_price():
    out = calc_duty({"question": "coffee CIF 4.50", "ncm_aec": 10, "precio_ref": 9999})
    assert out["impuestos_estimados"] == pytest.approx(_taxes(4.50, 0.45, 0.135))
    assert out["cif"] == pytest.approx(4.50)


def test_duty_ignores_fob_in_question():
    out = calc_duty({"question": "coffee FOB 4.50", "ncm_aec": 10})
    assert out["impuestos_estimados"] == 0


def test_parse_cif_from_question():
    from graph.nodes.calculate_costs import (
        parse_cantidad,
        parse_cif,
        parse_iibb_rate,
        parse_inscripto,
        parse_iva_rate,
        parse_origen,
        parse_provincia,
        strip_cif_clause,
    )

    assert parse_cif("green coffee beans CIF 4.50") == pytest.approx(4.50)
    assert parse_cif("café cif: 4,50") == pytest.approx(4.50)
    assert parse_cif("green coffee beans") is None
    assert parse_cif("coffee FOB 4.50") is None
    assert parse_origen("bombas CIF 100 origen China") == "China"
    assert parse_cantidad("pelotas CIF 100 200 unidades") == (200.0, "unidad")
    assert parse_cantidad("café CIF 4.50") is None
    assert parse_inscripto("coffee CIF 100") is False
    assert parse_inscripto("coffee CIF 100 responsable inscripto") is True
    assert parse_inscripto("coffee CIF 100 no inscripto") is False
    assert parse_inscripto("coffee CIF 100 consumo particular") is False
    assert parse_iva_rate("coffee CIF 100") == pytest.approx(21)
    assert parse_iva_rate("coffee CIF 100 IVA 10.5") == pytest.approx(10.5)
    assert parse_iva_rate("coffee CIF 100 IVA exento") == pytest.approx(0)
    assert parse_provincia("coffee CIF 100") is None
    assert parse_provincia("coffee CIF 100 provincia CABA") == "CABA"
    assert parse_provincia("coffee CIF 100 provincia Buenos Aires origen China") == "Buenos Aires"
    assert parse_provincia("coffee CIF 100 provincia Tierra del Fuego") == "Tierra del Fuego"
    assert parse_iibb_rate("coffee CIF 100") is None
    assert parse_iibb_rate("coffee CIF 100 IIBB 4") == pytest.approx(4)
    assert "CIF" not in strip_cif_clause("triciclo plegable CIF 223 USD")
    assert "223" not in strip_cif_clause("triciclo plegable CIF 223 USD")
    assert "China" not in strip_cif_clause("bombas CIF 100 origen China")
    assert "inscripto" not in strip_cif_clause("café CIF 100 responsable inscripto").lower()


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


def test_duty_adds_ad_valorem_when_origin_matches():
    medida = {
        "producto": "Bombas de agua",
        "origen": "China",
        "medida": "Derecho antidumping ad valorem de 246%.",
        "kind": "ad_valorem",
    }
    out = calc_duty(
        {
            "question": "bombas CIF 100 origen China",
            "ncm_aec": 10,
            "ncm_medidas": [medida],
        }
    )
    assert out["cif"] == 100
    assert out["origen"] == "China"
    assert out["impuestos_estimados"] == pytest.approx(_taxes(100, 10, 3, 246))


def test_duty_skips_ad_without_origin_and_skips_specific():
    ad = {
        "producto": "Bombas",
        "origen": "China",
        "medida": "Derecho antidumping ad valorem de 246%.",
        "kind": "ad_valorem",
    }
    specific = {
        "producto": "Pelotas de tenis",
        "origen": "China, Filipinas, Tailandia",
        "medida": "Derechos específicos: China: U$S 0,46 por unidad.",
        "kind": "especifico",
    }
    no_origin = calc_duty(
        {"question": "bombas CIF 100", "ncm_aec": 10, "ncm_medidas": [ad]}
    )
    assert no_origin["impuestos_estimados"] == pytest.approx(_taxes(100, 10, 3))
    assert "falta origen" in no_origin["costos_asociados"]
    tennis = calc_duty(
        {
            "question": "pelotas CIF 100 origen China",
            "ncm_aec": 0,
            "ncm_medidas": [specific],
        }
    )
    assert tennis["impuestos_estimados"] == pytest.approx(_taxes(100, 0, 3))
    assert "falta cantidad" in tennis["costos_asociados"]


def test_duty_multiplies_specific_when_quantity_matches():
    specific = {
        "producto": "Pelotas de tenis",
        "origen": "China, Filipinas, Tailandia",
        "medida": (
            "Derechos específicos: China: U$S 0,46 por unidad, "
            "Tailandia: U$S 0,21 por unidad."
        ),
        "kind": "especifico",
    }
    out = calc_duty(
        {
            "question": "pelotas CIF 100 origen China 200 unidades",
            "ncm_aec": 0,
            "ncm_medidas": [specific],
        }
    )
    assert out["cantidad"] == 200
    assert out["unidad"] == "unidad"
    assert out["impuestos_estimados"] == pytest.approx(_taxes(100, 0, 3, 200 * 0.46))


def test_duty_skips_ambiguous_specific_even_with_quantity():
    medida = {
        "producto": "Planchas",
        "origen": "China",
        "medida": (
            "Derecho antidumping específico de US$ 13,22 por unidad a las "
            "planchas secas, y de US$ 15,41 por unidad a las planchas a vapor."
        ),
        "kind": "especifico",
    }
    out = calc_duty(
        {
            "question": "planchas CIF 100 origen China 10 unidades",
            "ncm_aec": 0,
            "ncm_medidas": [medida],
        }
    )
    assert out["impuestos_estimados"] == pytest.approx(_taxes(100, 0, 3))
    assert "ambiguo" in out["costos_asociados"]


def test_estadistica_cap_and_mercosur_exemption():
    from graph.nodes.calculate_costs import calc_estadistica

    amount, note = calc_estadistica(4.50, None)
    assert amount == pytest.approx(0.135)
    capped, cap_note = calc_estadistica(10_000, "China")
    assert capped == pytest.approx(180)
    assert "tope" in cap_note
    zero, mercosur_note = calc_estadistica(10_000, "Brasil")
    assert zero == 0
    assert "Mercosur" in mercosur_note


def test_iva_is_21_percent_of_cif_plus_duties():
    from graph.nodes.calculate_costs import calc_iva

    amount, note = calc_iva(100, 10, 3, 0)
    assert amount == pytest.approx(23.73)
    assert "21" in note
    out = calc_duty({"question": "coffee CIF 100", "ncm_aec": 0})
    assert out["iva"] == pytest.approx(103 * 0.21)
    assert out["iva_percepcion"] == pytest.approx(103 * 0.20)
    assert out["ganancias"] == pytest.approx(103 * 0.11)
    assert out["inscripto"] is False
    assert out["impuestos_estimados"] == pytest.approx(_taxes(100, 0, 3))
    assert "Percepción IVA" in out["costos_asociados"]
    assert "Percepción Ganancias" in out["costos_asociados"]


def test_iva_reducido_halves_percepcion():
    out = calc_duty({"question": "ibuprofeno CIF 100 IVA 10.5", "ncm_aec": 0})
    assert out["iva"] == pytest.approx(103 * 0.105)
    assert out["iva_percepcion"] == pytest.approx(103 * 0.10)
    assert out["impuestos_estimados"] == pytest.approx(
        _taxes(100, 0, 3, iva_rate=10.5)
    )


def test_ganancias_particular_and_cvdi():
    particular = calc_duty(
        {"question": "coffee CIF 100 consumo particular", "ncm_aec": 0}
    )
    assert particular["inscripto"] is False
    assert particular["ganancias"] == pytest.approx(103 * 0.11)
    assert particular["impuestos_estimados"] == pytest.approx(
        _taxes(100, 0, 3, ganancias_rate=11)
    )
    ri = calc_duty({"question": "coffee CIF 100 responsable inscripto", "ncm_aec": 0})
    assert ri["inscripto"] is True
    assert ri["ganancias"] == pytest.approx(103 * 0.06)
    cvdi = calc_duty(
        {"question": "coffee CIF 100 responsable inscripto CVDI", "ncm_aec": 0}
    )
    assert cvdi["inscripto"] is True
    assert cvdi["ganancias"] == pytest.approx(103 * 0.03)
    excluded = calc_duty(
        {"question": "coffee CIF 100 certificado de exclusión", "ncm_aec": 0}
    )
    assert excluded["ganancias"] == pytest.approx(0)


def test_iibb_zero_without_province_and_applies_when_given():
    none = calc_duty({"question": "coffee CIF 100", "ncm_aec": 0})
    assert none["iibb"] == 0
    assert none["provincia"] == ""
    assert "falta provincia" in none["costos_asociados"]
    caba = calc_duty({"question": "coffee CIF 100 provincia CABA", "ncm_aec": 0})
    assert caba["provincia"] == "CABA"
    assert caba["iibb"] == pytest.approx(103 * 0.03)
    assert caba["impuestos_estimados"] == pytest.approx(
        _taxes(100, 0, 3, iibb_rate=3)
    )
    pba = calc_duty(
        {"question": "coffee CIF 100 provincia Buenos Aires", "ncm_aec": 0}
    )
    assert pba["iibb"] == pytest.approx(103 * 0.035)
    override = calc_duty({"question": "coffee CIF 100 IIBB 4", "ncm_aec": 0})
    assert override["iibb"] == pytest.approx(103 * 0.04)
    unknown = calc_duty({"question": "coffee CIF 100 provincia Atlántida", "ncm_aec": 0})
    assert unknown["iibb"] == 0
    assert unknown["provincia"] == ""
    assert "no reconocida" in unknown["costos_asociados"]


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
    from graph.nodes.web_search_hab import hab_domains, is_official_hab_url

    assert is_official_hab_url("https://www.argentina.gob.ar/senasa")
    assert is_official_hab_url("https://ejemplo.gob.ar/senasa")
    assert is_official_hab_url("https://www.mercosur.int/ncm")
    assert not is_official_hab_url("https://es.accio.com/plp/triciclo")
    assert not is_official_hab_url("https://www.mercadolibre.com.ar/triciclo")
    assert not is_official_hab_url("")
    assert hab_domains("ibuprofeno 400 mg comprimidos CIF 12") == ["anmat.gob.ar"]
    assert hab_domains("purebred breeding horse CIF 1000") == ["senasa.gob.ar"]
    assert hab_domains("triciclo plegable CIF 223") == ["argentina.gob.ar"]


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


def test_hab_retries_official_domains_when_first_search_is_shops(monkeypatch):
    shop = {
        "title": "Accio",
        "url": "https://es.accio.com/plp/ibuprofeno",
        "content": "Comprar ibuprofeno.",
    }
    official = {
        "title": "ANMAT",
        "url": "https://www.argentina.gob.ar/anmat",
        "content": "Inscripción en el Registro de Especialidades Medicinales.",
    }
    calls = []

    def _invoke(payload):
        calls.append(payload)
        if len(calls) == 1:
            return {"results": [shop]}
        return {"results": [shop, official]}

    monkeypatch.setattr(
        web_search_mod,
        "tavily",
        type("T", (), {"invoke": staticmethod(_invoke)})(),
    )
    out = web_search_hab(
        {"question": "ibuprofeno 400 mg comprimidos recubiertos CIF 12"}
    )
    assert len(calls) == 2
    domains = ["anmat.gob.ar"]
    assert calls[0].get("include_domains") == domains
    assert "site:.gob.ar" not in (calls[0].get("query") or "")
    assert calls[1].get("include_domains") == domains
    assert "comprimidos" not in (calls[1].get("query") or "").lower()
    urls = [doc.metadata["url"] for doc in out["hab_docs"]]
    assert urls == ["https://www.argentina.gob.ar/anmat"]


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


def test_parse_bcra_usd_a3500():
    from graph.nodes.search_price import parse_bcra_usd

    payload = {
        "status": 200,
        "results": [{
            "fecha": "2026-09-16",
            "detalle": [{"codigoMoneda": "USD", "descripcion": "DOLAR E.E.U.U.", "tipoCotizacion": 1513.5}],
        }],
    }
    rate, fecha = parse_bcra_usd(payload)
    assert rate == pytest.approx(1513.5)
    assert fecha == "2026-09-16"
    assert parse_bcra_usd({"results": []}) is None


def test_fetch_usd_ars_falls_back(monkeypatch):
    import urllib.error

    from graph.consts import USD_ARS_RATE
    from graph.nodes.search_price import fetch_usd_ars_rate

    def boom(*_a, **_k):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(search_price_mod.urllib.request, "urlopen", boom)
    rate, note = fetch_usd_ars_rate()
    assert rate == USD_ARS_RATE
    assert "BCRA no disponible" in note


def test_search_price_ars_uses_bcra(monkeypatch):
    monkeypatch.setattr(
        search_price_mod,
        "tavily",
        type("T", (), {"invoke": staticmethod(lambda _: {"results": [{"title": "t", "content": "$ 15135"}]})})(),
    )
    monkeypatch.setattr(
        search_price_mod,
        "price_chain",
        type("C", (), {"invoke": staticmethod(lambda _: type("R", (), {"price": 15135.0, "currency": "ARS", "motive": "x"})())})(),
    )
    monkeypatch.setattr(
        search_price_mod,
        "fetch_usd_ars_rate",
        lambda: (1513.5, "BCRA A3500 2026-09-16"),
    )
    out = search_price({"question": "ibuprofeno", "ncm": "3004.90.69", "ncm_descripcion": "x"})
    assert out["precio_ref"] == pytest.approx(10.0)
    assert "BCRA A3500 2026-09-16" in out["precio_info"]


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
    assert out["impuestos_estimados"] == pytest.approx(_taxes(1000, 0, 30))
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



