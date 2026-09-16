import re

from graph.consts import ESTADISTICA_CAPS, ESTADISTICA_RATE, MERCOSUR_ORIGINS
from graph.state import GraphState
from ncm.medidas import fold, origin_matches, rate_for_origin

_NUM = r"(\d+(?:[.,]\d+)?)"
CIF_RE = re.compile(rf"\bcif\s*[:=]?\s*{_NUM}", re.I)
ORIGEN_RE = re.compile(
    r"\b(?:origen|origin|procedencia)\s*[:=]?\s*([A-Za-zÁÉÍÓÚáéíóúñüÑ]+(?:\s+[A-Za-zÁÉÍÓÚáéíóúñüÑ]+)?)",
    re.I,
)
VALUE_CLAUSE_RE = re.compile(
    rf"\b(?:cif|fob|flete|freight|seguro|insurance)\s*[:=]?\s*{_NUM}(?:\s*usd)?"
    r"|\b(?:origen|origin|procedencia)\s*[:=]?\s*[A-Za-zÁÉÍÓÚáéíóúñüÑ]+(?:\s+[A-Za-zÁÉÍÓÚáéíóúñüÑ]+)?",
    re.I,
)


def parse_cif(question: str) -> float | None:
    match = CIF_RE.search(question or "")
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def parse_origen(question: str) -> str | None:
    match = ORIGEN_RE.search(question or "")
    if not match:
        return None
    return match.group(1).strip()


def strip_cif_clause(question: str) -> str:
    text = VALUE_CLAUSE_RE.sub("", question or "")
    return re.sub(r"\s+", " ", text).strip(" ,;-")


strip_fob_clause = strip_cif_clause


def is_mercosur_origin(origen: str | None) -> bool:
    key = fold(origen or "").replace(" ", "")
    if not key:
        return False
    return any(key == m or key in m or m in key for m in MERCOSUR_ORIGINS)


def estadistica_cap(cif: float) -> float:
    for limit, cap in ESTADISTICA_CAPS:
        if cif <= limit:
            return cap
    return ESTADISTICA_CAPS[-1][1]


def calc_estadistica(cif: float, origen: str | None) -> tuple[float, str]:
    """3 % of CIF, capped (Decree 1140/2024). Mercosur origin is exempt."""
    if is_mercosur_origin(origen):
        return 0.0, f"Tasa de estadística 0 USD (origen Mercosur: {origen})"
    raw = cif * (ESTADISTICA_RATE / 100)
    cap = estadistica_cap(cif)
    amount = min(raw, cap)
    note = (
        f"Tasa de estadística {ESTADISTICA_RATE:g}% sobre CIF = {amount:g} USD"
        + (f" (tope {cap:g})" if amount < raw else "")
    )
    if not origen:
        note += " (extra-zona; si el origen es Mercosur, esta tasa es 0)"
    return amount, note


def calc_duty(state: GraphState) -> dict:
    question = state.get("question") or ""
    cif = parse_cif(question)
    if cif is None:
        print("no CIF in question, skip duty")
        return {"impuestos_estimados": 0}
    aec = state.get("ncm_aec") or 0
    die = cif * (aec / 100)
    origen = parse_origen(question)
    te, te_line = calc_estadistica(cif, origen)
    extra = 0.0
    lines = [
        f"CIF {cif:g} USD (ingresado por el usuario)",
        f"DIE {aec:g}% sobre CIF = {die:g} USD",
        te_line,
    ]
    if origen:
        lines.append(f"Origen {origen}")
    for medida in state.get("ncm_medidas") or []:
        lines.append(
            f"Medida {medida.get('producto') or '-'} / {medida.get('origen') or '-'}: "
            f"{medida.get('medida') or '-'}"
        )
        if not origen:
            lines.append("No se aplicó: falta origen en la pregunta.")
            continue
        listed = medida.get("origen") or ""
        if not origin_matches(origen, listed):
            lines.append(f"No aplica a origen {origen}.")
            continue
        rate = rate_for_origin(medida.get("medida") or "", listed, origen)
        if rate is not None:
            amount = cif * (rate / 100)
            extra += amount
            lines.append(
                f"Antidumping ad valorem {rate:g}% sobre CIF = {amount:g} USD"
            )
            if (medida.get("kind") or "") in {"especifico", "combinada", "min_fob"}:
                lines.append(
                    "Queda un tramo específico o valor mínimo sin liquidar (hace falta cantidad/unidad)."
                )
        else:
            lines.append(
                "Hay derecho específico o valor mínimo FOB; no se liquidó (hace falta cantidad/unidad)."
            )
    total = die + extra + te
    print("DUTY", total, "USD", f"(DIE {die} + TE {te} + extra {extra} of CIF {cif})")
    print("LANDED", cif + total, "USD")
    return {
        "impuestos_estimados": total,
        "cif": cif,
        "origen": origen or "",
        "costos_asociados": "\n".join(lines),
    }
