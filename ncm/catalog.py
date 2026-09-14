"""NCM catalog and lookup tools (without RAG)."""

from __future__ import annotations

import json
import re
from functools import cached_property
from pathlib import Path
from typing import Any

from ncm.parser import CATALOG_PATH, parse_poc, save_catalog

def _norm(code: str) -> str:
    return code.replace(" ", "")


class NcmCatalog:
    def __init__(self, data: dict[str, Any]):
        self.data = data
        self._chapter = {c["codigo"]: c for c in data["chapters"]}
        self._by_code = {_norm(n["codigo"]): n for n in data["nodes"]}

    @classmethod
    def from_pdf(cls) -> "NcmCatalog":
        catalog = parse_poc()
        save_catalog(catalog)
        return cls(catalog)

    @classmethod
    def from_json(cls, path: Path = CATALOG_PATH) -> "NcmCatalog":
        if not path.exists():
            return cls.from_pdf()
        return cls(json.loads(path.read_text(encoding="utf-8")))

    @property
    def rgi(self) -> str:
        return self.data["rgi"]

    @cached_property
    def chapters(self) -> list[dict[str, Any]]:
        return list(self.data["chapters"])

    def search_chapters(self, query: str) -> list[dict[str, str]]:
        """Returns the chapters of the POC catalog; LLM chooses, not the score."""
        q = set(re.findall(r"\w+", query.lower()))
        ranked = []
        for ch in self.chapters:
            blob = f"{ch['titulo']} {ch['notas']}".lower()
            words = set(re.findall(r"\w+", blob))
            score = len(q & words)
            ranked.append(
                {
                    "chapter": ch["codigo"],
                    "title": ch["titulo"],
                    "score": score,
                }
            )
        ranked.sort(key=lambda r: r["score"], reverse=True)
        return ranked

    def get_notes(self, chapter: str) -> dict[str, str]:
        """Returns the notes for a chapter.
        
        Args:
            chapter: The chapter code, e.g. "01" or "09".

        Returns:
            A dictionary with the chapter code, title, chapter notes, and section notes.
        """
        ch = self._chapter[_norm(chapter).zfill(2)]
        return {
            "chapter": ch["codigo"],
            "title": ch["titulo"],
            "chapter_notes": ch["notas"],
            "section_notes": ch.get("notas_seccion") or "",
        }

    def list_headings(self, chapter: str) -> list[dict[str, Any]]:
        cap = _norm(chapter).zfill(2)
        headings: dict[str, str] = {}
        for node in self.data["nodes"]:
            if node["capitulo"] != cap:
                continue
            if node["nivel"] == 4:
                headings[node["codigo"]] = node["descripcion"]
            elif node["nivel"] == 6 and node["codigo"].endswith(".00"):
                headings.setdefault(node["partida"], node["descripcion"])
        for item in self.data["items"]:
            if item["capitulo"] == cap:
                headings.setdefault(item["partida"], item["descripcion_completa"])
        return [{"heading": k, "description": v} for k, v in headings.items()]

    def list_items(self, heading: str) -> list[dict[str, Any]]:
        p = _norm(heading)
        return [
            {
                "ncm": node["codigo"],
                "description": node["descripcion"],
                "full_description": node["descripcion_completa"],
                "aec": node["aec"],
                "re": node["re"],
            }
            for node in self.data["items"]
            if node["partida"] == p
        ]

    def get_ncm(self, code: str) -> dict[str, Any] | None:
        node = self._by_code.get(_norm(code))
        if not node or node["nivel"] != 8 or node["aec"] is None:
            return None
        return dict(node)
