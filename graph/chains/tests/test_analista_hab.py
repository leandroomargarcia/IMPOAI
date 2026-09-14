import importlib

from dotenv import load_dotenv

load_dotenv()

from langchain_core.documents import Document

from graph.chains.analista_hab import analista_hab_chain, format_hab_sources

mod = importlib.import_module("graph.nodes.analista_hab")

ANMAT_DOC = Document(
    page_content="La importación de suplementos dietarios requiere inscripción previa en ANMAT.",
    metadata={"url": "https://ejemplo.gob.ar/anmat", "title": "ANMAT"},
)
LNA_DOC = Document(
    page_content="Algunas posiciones arancelarias están alcanzadas por licencia no automática.",
    metadata={"url": "https://ejemplo.gob.ar/lna", "title": "LNA"},
)


def test_analista_sin_docs():
    out = mod.analista_hab({"question": "importar suplementos", "hab_docs": []})
    assert "No hay fuentes" in out["hab_info"]


def test_format_hab_sources_numera_desde_uno():
    text = format_hab_sources([ANMAT_DOC, LNA_DOC])
    assert text.startswith("[1]")
    assert "[2]" in text
    assert "https://ejemplo.gob.ar/anmat" in text


def test_analista_resuelve_urls(monkeypatch):
    docs = [ANMAT_DOC, LNA_DOC]

    class Fake:
        requisitos = [
            type("R", (), {"texto": "Inscripción ANMAT", "source_ids": [1]})()
        ]
        resumen = "Hay un requisito."

    monkeypatch.setattr(
        mod,
        "analista_hab_chain",
        type("C", (), {"invoke": staticmethod(lambda _: Fake())})(),
    )

    out = mod.analista_hab({"question": "importar suplementos", "hab_docs": docs})
    assert "https://ejemplo.gob.ar/anmat" in out["hab_info"]
    assert "https://ejemplo.gob.ar/lna" not in out["hab_info"]


def test_analista_source_id_invalido(monkeypatch):
    class Fake:
        requisitos = [
            type("R", (), {"texto": "Algo inventado", "source_ids": [99]})()
        ]
        resumen = "Sin respaldo."

    monkeypatch.setattr(
        mod,
        "analista_hab_chain",
        type("C", (), {"invoke": staticmethod(lambda _: Fake())})(),
    )

    out = mod.analista_hab({"question": "importar suplementos", "hab_docs": [ANMAT_DOC]})
    assert "fuente no encontrada" in out["hab_info"]
    assert "https://ejemplo.gob.ar/anmat" not in out["hab_info"]


def test_analista_hab_chain_extrae_de_fuentes():
    """Llama al LLM de verdad (como generation_grader_yes del curso)."""
    res = analista_hab_chain.invoke(
        {
            "question": "Quiero importar suplementos dietarios a Argentina",
            "sources": format_hab_sources([ANMAT_DOC, LNA_DOC]),
        }
    )
    ids = {sid for req in res.requisitos for sid in req.source_ids}
    assert res.requisitos, "La chain debería extraer al menos un requisito"
    assert ids <= {1, 2}, f"source_ids fuera de rango: {ids}"
    assert any("anmat" in req.texto.lower() for req in res.requisitos)
