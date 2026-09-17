"""Numeric NCM limits vs the product question (no LLM).

If the question has 20 t/h and an item says "superior a 45 t por hora", drop it.
CIF / FOB / IVA amounts are ignored. Unknown units are left alone.
"""

from __future__ import annotations

import re
from typing import Any

_ACCENT = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")
_NUM_INNER = r"\d+(?:[.,]\d+)?"
_NUM = rf"({_NUM_INNER})"
_CLAUSE_RE = re.compile(
    r"\b(?:cif|fob|iva|iibb)\s*[:=]?\s*\d+(?:[.,]\d+)?\s*%?"
    r"|\b\d+(?:[.,]\d+)?\s*usd\b",
    re.I,
)
# Longer units first so "t por hora" is not parsed as bare "t".
_UNITS = (
    ("t/h", r"t(?:oneladas?)?\s*(?:por|/)\s*h(?:oras?)?|t/h"),
    ("kg", r"kilogramos?|kgs?\b"),
    ("t", r"toneladas?|\bt\b"),
    ("kw", r"k(?:ilo)?w(?:atts?)?|\bkw\b"),
    ("cv", r"\bcv\b|\bhp\b"),
    ("cm3", r"cm(?:3|³)|centimetros?\s+cubicos?|\bcc\b"),
    ("mm", r"milimetros?|\bmm\b"),
    ("m", r"metros?(?:\s+lineales?)?|\bm\b"),
)
_UNIT_ALT = "|".join(f"(?P<u{i}>{pat})" for i, (_, pat) in enumerate(_UNITS))
_SPEC_RE = re.compile(rf"{_NUM}\s*(?:{_UNIT_ALT})", re.I)
_BOUND_RE = re.compile(
    rf"(?P<op>no\s+superior\s+a|superior(?:\s+o\s+igual)?\s+a|"
    rf"inferior(?:\s+o\s+igual)?\s+a|de\s+mas\s+de|mas\s+de|menos\s+de|hasta)"
    rf"\s*(?P<num>{_NUM_INNER})\s*(?:{_UNIT_ALT})",
    re.I,
)


def _fold(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").translate(_ACCENT).lower()).strip()


def _num(raw: str) -> float:
    return float(raw.replace(",", "."))


def _unit_from_match(match: re.Match) -> str:
    for i, (key, _) in enumerate(_UNITS):
        if match.group(f"u{i}"):
            return key
    return ""


def strip_value_clauses(question: str) -> str:
    return _CLAUSE_RE.sub(" ", question or "")


def extract_specs(question: str) -> list[tuple[float, str]]:
    text = _fold(strip_value_clauses(question))
    out: list[tuple[float, str]] = []
    for match in _SPEC_RE.finditer(text):
        unit = _unit_from_match(match)
        if unit:
            out.append((_num(match.group(1)), unit))
    return out


def extract_constraints(item_text: str) -> list[tuple[str, float, str]]:
    text = _fold(item_text)
    out: list[tuple[str, float, str]] = []
    for match in _BOUND_RE.finditer(text):
        unit = _unit_from_match(match)
        if not unit:
            continue
        out.append((_op(match.group("op")), _num(match.group("num")), unit))
    return out


def _op(raw: str) -> str:
    key = _fold(raw)
    if "igual" in key or key == "hasta" or key.startswith("no superior"):
        return ">=" if key.startswith("superior") else "<="
    if key.startswith("inferior") or key.startswith("menos"):
        return "<"
    return ">"


def _holds(value: float, op: str, bound: float) -> bool:
    if op == ">":
        return value > bound
    if op == ">=":
        return value >= bound
    if op == "<":
        return value < bound
    return value <= bound


def item_conflicts(question: str, item_text: str) -> bool:
    """True if a comparable number in the question falls outside an item limit."""
    specs = extract_specs(question)
    constraints = extract_constraints(item_text)
    if not specs or not constraints:
        return False
    for op, bound, unit in constraints:
        values = [v for v, u in specs if u == unit]
        if not values:
            continue
        if not any(_holds(v, op, bound) for v in values):
            return True
    return False


def _item_text(item: dict[str, Any]) -> str:
    return (
        item.get("full_description")
        or item.get("descripcion")
        or item.get("description")
        or ""
    )


def filter_items(question: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept = [item for item in items if not item_conflicts(question, _item_text(item))]
    specs = extract_specs(question)
    units = {unit for _, unit in specs}
    specific = []
    for item in kept:
        constraints = extract_constraints(_item_text(item))
        if any(unit in units for _, _, unit in constraints):
            specific.append(item)
    if specific:
        return specific
    return kept or list(items)
