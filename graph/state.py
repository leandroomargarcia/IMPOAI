from typing import List, TypedDict

from langchain_core.documents import Document


class GraphState(TypedDict):
    """
    State of the graph.

    Attributes:
        question: The question that the user asked (invoke).
        ncm_chapter: NCM chapter (pick_chapter).
        ncm_notes: NCM notes (load_notes).
        ncm_heading: NCM heading (choose_heading).
        ncm_subheading: NCM subheading (choose_subheading).
        ncm_item: NCM item (choose_item).
        ncm: NCM code (fetch_ncm).
        ncm_aec: NCM AEC (grade_ncm).
        ncm_aec_flag: Mercosur BK / BIT label from the catalog (empty if none).
        ncm_descripcion: NCM description (grade_ncm).
        ncm_info: NCM classification (or why it failed).
        ncm_feedback: grader motive / miss reason.
        hab_docs: web search hits on import permits (web_search_hab).
        hab_info: extracted habilitation requirements (analista_hab).
        attempts: Number of attempts to classify the product.
        es_valido: groundedness del NCM (grade_generation)
        cif: CIF entered in the question (duty base; not derived from FOB)
        origen: country of origin parsed from the question (antidumping)
        cantidad: import quantity from the question (specific duty)
        unidad: unit for cantidad (unidad, kg, m, m2, par)
        ncm_medidas: CNCE trade-defense rows for this NCM
        inscripto: IVA-registered importer; True only if the question says so (default monotributista)
        provincia: Argentine province for IIBB (empty unless the question has it)
        iva_percepcion: RG 2937 VAT perception amount
        ganancias: RG 2281 income-tax perception amount
        iibb: IIBB perception by province (0 if no provincia)
        precio_ref: Argentine selling price converted to USD
        precio_info: human message (found price, or not found in Argentina)
        costos_asociados: line-by-line estimate (CIF, DIE, estadística, medidas, IVA, percepciones, IIBB)
        impuestos_estimados: DIE + estadística + medidas + IVA + percepciones + IIBB (calcular_costos)
        reporte_final: final report (orquestador)
        price_job_id: background Tavily job started at START (search_price_wait)
    """

    question: str
    ncm_chapter: str
    ncm_notes: str
    ncm_heading: str
    ncm_subheading: str
    ncm_item: str
    ncm: str
    ncm_aec: float
    ncm_aec_flag: str
    ncm_descripcion: str
    ncm_info: str
    ncm_feedback: str
    ncm_currency: str
    hab_docs: List[Document]
    hab_info: str
    attempts: int
    es_valido: bool
    cif: float
    origen: str
    cantidad: float
    unidad: str
    iva: float
    iva_percepcion: float
    ganancias: float
    iibb: float
    inscripto: bool
    provincia: str
    ncm_medidas: list
    precio_ref: float
    precio_info: str
    costos_asociados: str
    impuestos_estimados: float
    reporte_final: str
    price_job_id: str
