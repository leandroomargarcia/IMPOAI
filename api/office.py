"""One invoke = one graph run. Shared by POST /run and the chat layer."""

from langfuse import get_client
from langfuse.langchain import CallbackHandler

from graph.graph import app as office


PUBLIC_KEYS = (
    "ncm",
    "ncm_descripcion",
    "es_valido",
    "attempts",
    "cif",
    "impuestos_estimados",
    "costos_asociados",
    "precio_ref",
    "precio_info",
    "hab_info",
    "reporte_final",
)


def public_result(out: dict) -> dict:
    pub = {key: out.get(key) for key in PUBLIC_KEYS}
    ncm = pub.get("ncm")
    if ncm:
        from graph.nodes.ncm_node import catalog

        pub["ncm_path"] = catalog.path_labels(ncm)
    return pub


def invoke_office(question: str, tags: list[str] | None = None) -> dict:
    handler = CallbackHandler()
    out = office.invoke(
        {"question": question, "attempts": 0},
        config={
            "callbacks": [handler],
            "metadata": {"langfuse_tags": tags or ["api"]},
        },
    )
    get_client().flush()
    return out
