from typing import List, TypedDict

from langchain_core.documents import Document


class GraphState(TypedDict):
    """
    State of the graph.

    Attributes:
        question: The question that the user asked (invoke).
        ncm_info: NCM classification (or why it failed).
        ncm_feedback: grader motive / miss reason.
        hab_docs: web search hits on import permits (web_search_hab).
        hab_info: extracted habilitation requirements (analista_hab).
        attempts: Number of attempts to classify the product.
        es_valido: groundedness del NCM (grade_generation)
        fob: customs value parsed from the question (not searched)
        precio_ref: Argentine selling price converted to USD
        precio_info: human message (found price, or not found in Argentina)
        costos_asociados: associated costs (desglose_costos)
        impuestos_estimados: AEC duty on FOB (calcular_costos)
        reporte_final: final report (orquestador)
    """

    question: str
    ncm_chapter: str
    ncm_notes: str
    ncm_heading: str
    ncm_subheading: str
    ncm_item: str
    ncm: str
    ncm_aec: float
    ncm_descripcion: str
    ncm_info: str
    ncm_feedback: str
    ncm_currency: str
    hab_docs: List[Document]
    hab_info: str
    attempts: int
    es_valido: bool
    fob: float
    precio_ref: float
    precio_info: str
    costos_asociados: str
    impuestos_estimados: float
    reporte_final: str
