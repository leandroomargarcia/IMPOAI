import re

from graph.state import GraphState

FOB_RE = re.compile(r"\bfob\s*[:=]?\s*(\d+(?:[.,]\d+)?)", re.I)
FOB_CLAUSE_RE = re.compile(
    r"\bfob\s*[:=]?\s*\d+(?:[.,]\d+)?(?:\s*usd)?",
    re.I,
)


def parse_fob(question: str) -> float | None:
    match = FOB_RE.search(question or "")
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def strip_fob_clause(question: str) -> str:
    text = FOB_CLAUSE_RE.sub("", question or "")
    return re.sub(r"\s+", " ", text).strip(" ,;-")


def calc_duty(state: GraphState) -> dict:
    fob = parse_fob(state.get("question") or "")
    if fob is None:
        print("no FOB in question, skip duty")
        return {"impuestos_estimados": 0}
    aec = state.get("ncm_aec") or 0
    duty = fob * (aec / 100)
    print("DUTY", duty, "USD", f"(AEC {aec}% of FOB {fob})")
    print("LANDED", fob + duty, "USD")
    return {"impuestos_estimados": duty, "fob": fob}
