"""CNCE/AFIP trade-defense measures (dumping): ad valorem, specific, min FOB.

Parses `docs/*medidas*.xlsx`. Does not hit the web.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zipfile import ZipFile

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
NCM_RE = re.compile(r"\d{4}\.\d{2}\.\d{2}")
RATE_RE = re.compile(
    r"([A-Za-zÁÉÍÓÚáéíóúñüÑ]+)(?:\s*:\s*|\s+)(\d+(?:[.,]\d+)?)\s*%"
)
PCT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
_ACCENT = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")
_STOP = {
    "de",
    "del",
    "la",
    "el",
    "un",
    "una",
    "hasta",
    "desde",
    "por",
    "y",
    "en",
    "los",
    "las",
    "para",
    "con",
    "ad",
    "valorem",
}


def fold(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").translate(_ACCENT).lower()).strip()


def origin_matches(user: str, listed: str) -> bool:
    u = fold(user).replace(" ", "")
    if not u:
        return False
    parts = [
        fold(p).replace(" ", "")
        for p in re.split(r"[,;/]|\by\b", listed or "")
        if fold(p)
    ]
    return any(p and (p in u or u in p) for p in parts)


def parse_ncm_list(raw: str) -> list[str]:
    return NCM_RE.findall(raw or "")


def extract_ad_valorem(medida: str, origen: str) -> dict[str, float]:
    """Country-folded name -> percent. One unnamed % is assigned to every origin."""
    origins = [
        fold(p).replace(" ", "")
        for p in re.split(r"[,;/]|\by\b", origen or "")
        if fold(p)
    ]
    rates: dict[str, float] = {}
    for match in RATE_RE.finditer(medida or ""):
        name = fold(match.group(1)).replace(" ", "")
        if name in _STOP:
            continue
        if origins and not any(name in o or o in name for o in origins):
            continue
        rates[name] = float(match.group(2).replace(",", "."))
    if rates:
        return rates
    pcts = [float(x.replace(",", ".")) for x in PCT_RE.findall(medida or "")]
    if len(pcts) == 1:
        return {o: pcts[0] for o in origins} or {"_": pcts[0]}
    return {}


def rate_for_origin(medida: str, origen_listed: str, user_origin: str) -> float | None:
    if not origin_matches(user_origin, origen_listed):
        return None
    rates = extract_ad_valorem(medida, origen_listed)
    if not rates:
        return None
    u = fold(user_origin).replace(" ", "")
    for name, pct in rates.items():
        if name != "_" and (name in u or u in name):
            return pct
    if len(set(rates.values())) == 1:
        return next(iter(rates.values()))
    return None


def measure_kind(medida: str) -> str:
    text = fold(medida)
    specific = "especific" in text
    adval = "ad valorem" in text or bool(PCT_RE.search(medida or ""))
    minimum = "minimo" in text or "compromiso de precios" in text
    if specific and adval:
        return "combinada"
    if specific:
        return "especifico"
    if minimum and not adval:
        return "min_fob"
    if adval:
        return "ad_valorem"
    if minimum:
        return "min_fob"
    return "otro"


def _excel_date(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    try:
        serial = float(text)
    except ValueError:
        return text
    if serial < 20000:
        return text
    day = datetime(1899, 12, 30) + timedelta(days=int(serial))
    return day.date().isoformat()


def latest_medidas_xlsx(folder: Path = DOCS_DIR) -> Path | None:
    files = [
        p
        for p in folder.glob("*medidas*.xlsx")
        if p.is_file() and not p.name.startswith("~$")
    ]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def _shared_strings(z: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    out: list[str] = []
    for si in root.findall("m:si", NS):
        out.append("".join(t.text or "" for t in si.findall(".//m:t", NS)))
    return out


def _cell_value(cell: ET.Element, strings: list[str]) -> str:
    kind = cell.get("t")
    if kind == "s":
        v = cell.find("m:v", NS)
        if v is None or v.text is None:
            return ""
        return strings[int(v.text)]
    if kind == "inlineStr":
        return "".join(t.text or "" for t in cell.findall(".//m:t", NS))
    v = cell.find("m:v", NS)
    return v.text if v is not None and v.text else ""


def parse_medidas_xlsx(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with ZipFile(path) as z:
        strings = _shared_strings(z)
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        for row in sheet.findall("m:sheetData/m:row", NS):
            cells: dict[str, str] = {}
            for cell in row.findall("m:c", NS):
                ref = cell.get("r") or ""
                col = "".join(ch for ch in ref if ch.isalpha())
                cells[col] = _cell_value(cell, strings)
            ncm_codes = parse_ncm_list(cells.get("E") or "")
            if not ncm_codes:
                continue
            medida = (cells.get("G") or "").strip()
            origen = (cells.get("D") or "").strip()
            rec = {
                "tipo": (cells.get("B") or "").strip(),
                "producto": (cells.get("C") or "").strip(),
                "origen": origen,
                "ncm": ncm_codes,
                "procedimiento": (cells.get("F") or "").strip(),
                "medida": medida,
                "resolucion": (cells.get("H") or "").strip(),
                "vencimiento": _excel_date(cells.get("I") or ""),
                "kind": measure_kind(medida),
                "ad_valorem": extract_ad_valorem(medida, origen),
            }
            rows.append(rec)
    return rows


@dataclass
class MedidasIndex:
    source: str = ""
    by_ncm: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def for_ncm(self, code: str) -> list[dict[str, Any]]:
        key = (code or "").replace(" ", "")
        return list(self.by_ncm.get(key) or [])


def load_medidas(folder: Path = DOCS_DIR) -> MedidasIndex:
    path = latest_medidas_xlsx(folder)
    index = MedidasIndex()
    if not path:
        return index
    index.source = path.name
    for rec in parse_medidas_xlsx(path):
        for ncm in rec["ncm"]:
            index.by_ncm.setdefault(ncm, []).append(rec)
    return index
