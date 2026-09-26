"""HTTP door: chat (SSE) + one-shot office (POST /run)."""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from api.chat import router as chat_router
from api.guardrails import require_cif
from api.office import invoke_office, public_result
import asyncio

load_dotenv()

api = FastAPI(title="IMPOAI", version="0.2.0")
api.include_router(chat_router)

CHAT_DIR = Path(__file__).resolve().parent.parent / "chat"


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


def _to_run_out(out: dict) -> RunOut:
    pub = public_result(out)
    return RunOut(
        ncm=pub.get("ncm") or None,
        ncm_descripcion=pub.get("ncm_descripcion") or None,
        es_valido=pub.get("es_valido"),
        attempts=pub.get("attempts"),
        cif=pub.get("cif"),
        impuestos_estimados=pub.get("impuestos_estimados"),
        costos_asociados=pub.get("costos_asociados") or None,
        precio_ref=pub.get("precio_ref"),
        precio_info=pub.get("precio_info") or None,
        hab_info=pub.get("hab_info") or None,
        reporte_final=pub.get("reporte_final") or None,
    )


@api.get("/health")
def health() -> dict:
    return {"ok": True}


@api.get("/")
def chat_home() -> FileResponse:
    return FileResponse(CHAT_DIR / "index.html")


@api.post("/run", response_model=RunOut)
async def run(body: RunIn) -> RunOut:
    err = require_cif(body.question)
    if err:
        raise HTTPException(status_code=400, detail=err)
    out = await asyncio.to_thread(invoke_office, body.question, ["api"])
    return _to_run_out(out)
