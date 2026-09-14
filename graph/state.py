from typing import List, TypedDict

from langchain_core.documents import Document


class GraphState(TypedDict):
    """
    State of the graph.

    Attributes:
        question: The question that the user asked (invoke).
        ncm_info: NCM classification.
        hab_docs: web search hits on import permits (web_search_hab).
        hab_info: extracted habilitation requirements (analista_hab).
        attempts: Number of attempts to classify the product.
        es_valido: groundedness del NCM (grade_generation)
        precio_ref: price reference (buscar_precio)
        costos_asociados: associated costs (desglose_costos)
        impuestos_estimados: estimated taxes (calcular_costos)
        reporte_final: final report (generar_reporte)
    """

    question: str
    ncm_chapter: str
    ncm_notes: str
    ncm_heading: str
    ncm_item: str
    ncm: str
    ncm_aec: float
    ncm_descripcion: str
    ncm_currency: str
    hab_docs: List[Document]
    hab_info: str
    attempts: int
    es_valido: bool
    precio_ref: float
    costos_asociados: str
    impuestos_estimados: float
    reporte_final: str
