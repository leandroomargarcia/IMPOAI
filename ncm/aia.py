"""Arancel Integrado Aduanero (AIA) dumps from AFIP/ARCA.

Parses `docs/nomenclador_*.txt` and `docs/capitulo_*.txt`. Does not hit the web.
Rates on SIM 12-digit rows: DEX, RE (not the import statistical fee), DIE (import duty / AEC), II.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
NCM8_RE = re.compile(r"^(\d{4}\.\d{2}\.\d{2})")


def _parse_rate(raw: str) -> float | None:
    text = (raw or "").strip()
    if not text:
        return None
    return float(text)


def _ncm8(code: str) -> str | None:
    match = NCM8_RE.match(code.replace(" ", ""))
    return match.group(1) if match else None


def latest_docs_file(prefix: str, folder: Path = DOCS_DIR) -> Path | None:
    files = [p for p in folder.glob(f"{prefix}_*.txt") if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


@dataclass
class AiaIndex:
    source: str = ""
    # 8-digit NCM -> rates + description
    by_ncm: dict[str, dict[str, Any]] = field(default_factory=dict)
    chapter_notes: dict[str, str] = field(default_factory=dict)

    def die(self, code: str) -> float | None:
        row = self.by_ncm.get(code) or self.by_ncm.get(_ncm8(code) or "")
        if not row:
            return None
        return row.get("die")


def parse_nomenclador(text: str) -> dict[str, dict[str, Any]]:
    """Group SIM rows under the 8-digit NCM. DIE is the import duty (AEC)."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    parents: dict[str, str] = {}

    for raw in text.splitlines():
        parts = raw.split("@")
        if len(parts) < 11 or parts[0].strip() != "2":
            continue
        sim = parts[1].strip()
        ncm = _ncm8(sim)
        if not ncm:
            continue
        desc = (parts[10] if len(parts) > 10 else "").strip()
        die = _parse_rate(parts[4])
        if die is None:
            if desc:
                parents[ncm] = desc
            continue
        grouped.setdefault(ncm, []).append(
            {
                "sim": sim,
                "dex": _parse_rate(parts[2]),
                "re": _parse_rate(parts[3]),
                "die": die,
                "ii": _parse_rate(parts[6]),
                "description": desc,
            }
        )

    out: dict[str, dict[str, Any]] = {}
    for ncm, rows in grouped.items():
        dies = [r["die"] for r in rows if r["die"] is not None]
        die = dies[0] if dies else None
        if dies and len(set(dies)) > 1:
            prefer = next(
                (r["die"] for r in rows if ".900" in r["sim"] and r["die"] is not None),
                None,
            )
            die = prefer if prefer is not None else dies[0]
        out[ncm] = {
            "ncm": ncm,
            "description": parents.get(ncm) or (rows[0]["description"] if rows else ""),
            "die": die,
            "dex": rows[0]["dex"] if rows else None,
            "re": rows[0]["re"] if rows else None,
            "ii": rows[0]["ii"] if rows else None,
            "die_min": min(dies) if dies else None,
            "die_max": max(dies) if dies else None,
            "sim_count": len(rows),
        }
    for ncm, desc in parents.items():
        out.setdefault(ncm, {"ncm": ncm, "description": desc, "die": None, "sim_count": 0})
    return out


def parse_capitulo(text: str) -> dict[str, str]:
    notes: dict[str, str] = {}
    for raw in text.splitlines():
        parts = raw.split("@", 2)
        if len(parts) < 3 or parts[0].strip() != "1":
            continue
        cap = parts[1].strip().zfill(2)
        body = parts[2].strip()
        if cap == "00" or not body:
            continue
        notes[cap] = re.sub(r"[ \t]+", " ", body)
    return notes


def load_aia(folder: Path = DOCS_DIR) -> AiaIndex:
    nom_path = latest_docs_file("nomenclador", folder)
    cap_path = latest_docs_file("capitulo", folder)
    index = AiaIndex()
    if nom_path:
        index.source = nom_path.name
        index.by_ncm = parse_nomenclador(nom_path.read_text(encoding="latin-1"))
    if cap_path:
        index.chapter_notes = parse_capitulo(cap_path.read_text(encoding="latin-1"))
    return index
