"""HTTP door to the NCM office. One POST = one graph.invoke."""

from dotenv import load_dotenv
from fastapi import FastAPI
from langfuse import get_client
from langfuse.langchain import CallbackHandler
from pydantic import BaseModel, Field

from graph.graph import app as office

load_dotenv()

api = FastAPI(title="IMPOAI", version="0.1.0")


class RunIn(BaseModel):
    question: str = Field(min_length=3)


class RunOut(BaseModel):
    ncm: str | None
    ncm_descripcion: str | None
    es_valido: bool | None
    attempts: int | None
    cif: float | None
    impuestos_estimados: float | None
    costos_asociados: str | None
    precio_ref: float | None
    precio_info: str | None
    hab_info: str | None
    reporte_final: str | None


@api.get("/health")
def health() -> dict:
    return {"ok": True}


@api.post("/run", response_model=RunOut)
def run(body: RunIn) -> RunOut:
    handler = CallbackHandler()
    out = office.invoke(
        {"question": body.question, "attempts": 0},
        config={
            "callbacks": [handler],
            "metadata": {"langfuse_tags": ["api"]},
        },
    )
    get_client().flush()
    return RunOut(
        ncm=out.get("ncm") or None,
        ncm_descripcion=out.get("ncm_descripcion") or None,
        es_valido=out.get("es_valido"),
        attempts=out.get("attempts"),
        cif=out.get("cif"),
        impuestos_estimados=out.get("impuestos_estimados"),
        costos_asociados=out.get("costos_asociados") or None,
        precio_ref=out.get("precio_ref"),
        precio_info=out.get("precio_info") or None,
        hab_info=out.get("hab_info") or None,
        reporte_final=out.get("reporte_final") or None,
    )
