import re

from graph.state import GraphState

_NUM = r"(\d+(?:[.,]\d+)?)"
CIF_RE = re.compile(rf"\bcif\s*[:=]?\s*{_NUM}", re.I)
VALUE_CLAUSE_RE = re.compile(
    rf"\b(?:cif|fob|flete|freight|seguro|insurance)\s*[:=]?\s*{_NUM}(?:\s*usd)?",
    re.I,
)


def parse_cif(question: str) -> float | None:
    match = CIF_RE.search(question or "")
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def strip_cif_clause(question: str) -> str:
    text = VALUE_CLAUSE_RE.sub("", question or "")
    return re.sub(r"\s+", " ", text).strip(" ,;-")


strip_fob_clause = strip_cif_clause


def calc_duty(state: GraphState) -> dict:
    cif = parse_cif(state.get("question") or "")
    if cif is None:
        print("no CIF in question, skip duty")
        return {"impuestos_estimados": 0}
    aec = state.get("ncm_aec") or 0
    duty = cif * (aec / 100)
    breakdown = (
        f"CIF {cif:g} USD (ingresado por el usuario)\n"
        f"DIE {aec:g}% sobre CIF = {duty:g} USD"
    )
    print("DUTY", duty, "USD", f"(DIE {aec}% of CIF {cif})")
    print("LANDED", cif + duty, "USD")
    return {
        "impuestos_estimados": duty,
        "cif": cif,
        "costos_asociados": breakdown,
    }
