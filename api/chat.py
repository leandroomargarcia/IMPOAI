"""Conversational layer. The chat LLM calls the office as a tool."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from api.guardrails import (
    Slots,
    is_jailbreak,
    is_ready,
    parse_user_cif,
    slots_hint,
    update_slots,
    wants_classify,
)
from api.office_tool import CLASSIFY_TOOL, TOOL_NAME, run_classify
from llm import chat_llm

router = APIRouter()

SESSIONS: dict[str, dict] = {}

SYSTEM = (
    "Sos IMPOAI. Respondés preguntas generales en español, claro y breve. "
    "Para una clasificación NCM / posición arancelaria / liquidación fiscal "
    "tenés la herramienta classify_ncm: usala cuando el usuario lo pida "
    "(clasificar, posición, partida, NCM, liquidar, estimar derechos). "
    "No inventes un NCM de 8 dígitos ni montos: eso sale de classify_ncm. "
    "Cada producto necesita su propio CIF. No clasifiques ni llames "
    "classify_ncm hasta que el usuario escriba CIF y un número en USD "
    "para ESA mercadería. No reutilices el CIF de un producto anterior "
    "ni inventes un cif_usd en la tool. "
    "Si pide clasificar y falta el CIF de este producto, pedilo. "
    "Si este producto ya tiene CIF escrito por el usuario y pidió "
    "posición/clasificar/liquidar, llamá classify_ncm en este turno: "
    "no pidas confirmación. "
    "No trates el resultado como un despacho AFIP / SIM / María."
)


class ChatIn(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


def _session(session_id: str) -> dict:
    return SESSIONS.setdefault(
        session_id,
        {"messages": [], "slots": Slots()},
    )


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _wrap(out: dict) -> str:
    ncm = out.get("ncm") or "sin NCM"
    tax = out.get("impuestos_estimados")
    cif = out.get("cif")
    tax_s = f"{tax:g}" if isinstance(tax, (int, float)) else "—"
    cif_s = f"{cif:g}" if isinstance(cif, (int, float)) else "—"
    item = ""
    partida = ""
    for row in out.get("ncm_path") or []:
        text = (row.get("text") or "").strip()
        if row.get("level") == "Ítem" and text:
            item = text
        elif row.get("level") == "Partida" and text:
            partida = text
    desc = out.get("ncm_descripcion") or ""
    if not item:
        item = desc.split(" / ")[-1].strip() if desc else ""
    if not partida:
        partida = desc.split(" / ")[0].strip() if desc else ""
    head = f"NCM {ncm}"
    bits = [bit for bit in (item, f"partida: {partida}" if partida and partida != item else "") if bit]
    if bits:
        head = f"NCM {ncm}: {'; '.join(bits)}"
    return (
        f"Listo. {head}. "
        f"Liquidación estimada {tax_s} USD sobre CIF {cif_s}. "
        "Esto es una estimación, no un despacho AFIP / SIM / María."
    )


def _history(session: dict) -> list:
    messages = [SystemMessage(SYSTEM)]
    for item in session["messages"]:
        if item["role"] == "user":
            messages.append(HumanMessage(item["content"]))
        elif item["role"] == "assistant":
            messages.append(AIMessage(item["content"]))
    messages.append(SystemMessage(slots_hint(session["slots"])))
    return messages


def _chunk_text(chunk) -> str:
    content = getattr(chunk, "content", "") or ""
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text") or "")
        return "".join(parts)
    return content if isinstance(content, str) else ""


def _tool_calls(acc) -> list[dict]:
    if acc is None:
        return []
    return list(getattr(acc, "tool_calls", None) or [])


async def _stream_text(text: str) -> AsyncIterator[str]:
    step = 24
    for i in range(0, len(text), step):
        yield _sse("token", text[i : i + step])
        await asyncio.sleep(0)


async def stream_agent(messages: list, force_tool: bool = False):
    """Yield (kind, payload): token str, then final assembled chunk."""
    if force_tool:
        bound = chat_llm.bind_tools([CLASSIFY_TOOL], tool_choice=TOOL_NAME)
    else:
        bound = chat_llm.bind_tools([CLASSIFY_TOOL])
    acc = None
    async for chunk in bound.astream(messages):
        acc = chunk if acc is None else acc + chunk
        text = _chunk_text(chunk)
        if text:
            yield ("token", text)
    yield ("final", acc)


async def _events(body: ChatIn) -> AsyncIterator[str]:
    session = _session(body.session_id)
    slots: Slots = session["slots"]
    text = body.message.strip()
    session["messages"].append({"role": "user", "content": text})

    if is_jailbreak(text):
        yield _sse("status", "chatting")
        msg = "No puedo cambiar mis instrucciones. Preguntame otra cosa."
        async for part in _stream_text(msg):
            yield part
        session["messages"].append({"role": "assistant", "content": msg})
        yield _sse("status", "done")
        return

    had_product = bool(slots.product)
    incoming_cif = parse_user_cif(text)
    update_slots(slots, text)
    yield _sse("status", "chatting")

    collected: list[str] = []
    acc = None
    try:
        force_tool = is_ready(slots) and (
            wants_classify(text) or (had_product and incoming_cif is not None)
        )
        async for kind, payload in stream_agent(_history(session), force_tool):
            if kind == "token":
                collected.append(payload)
                yield _sse("token", payload)
            else:
                acc = payload
    except Exception:
        fallback = (
            "No pude generar la respuesta. Reintentá o pedí clasificar "
            "con producto y CIF."
        )
        collected = [fallback]
        async for part in _stream_text(fallback):
            yield part
        session["messages"].append({"role": "assistant", "content": fallback})
        yield _sse("status", "done")
        return

    calls = [c for c in _tool_calls(acc) if c.get("name") == TOOL_NAME]
    if not calls:
        session["messages"].append(
            {"role": "assistant", "content": "".join(collected) or "OK."}
        )
        yield _sse("status", "done")
        return

    args = calls[0].get("args") or {}
    yield _sse("status", "classifying")
    wait = "Clasificando… llamo al office (tool classify_ncm)."
    async for part in _stream_text(wait):
        yield part

    try:
        result = await asyncio.to_thread(run_classify, args, slots)
    except Exception as exc:
        yield _sse("error", str(exc))
        yield _sse("status", "done")
        return

    if result.get("error"):
        yield _sse("status", "collecting")
        async for part in _stream_text(result["error"]):
            yield part
        session["messages"].append(
            {"role": "assistant", "content": result["error"]}
        )
        yield _sse("status", "done")
        return

    merged = result.pop("_slots", None)
    if merged is not None:
        session["slots"] = merged
    wrap = _wrap(result)
    async for part in _stream_text(wrap):
        yield part
    yield _sse("card", result)
    session["messages"].append({"role": "assistant", "content": wrap})
    yield _sse("status", "done")


@router.post("/chat")
async def chat(body: ChatIn) -> StreamingResponse:
    return StreamingResponse(
        _events(body),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
