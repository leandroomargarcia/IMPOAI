"""NCM catalog and lookup tools (without RAG)."""

from __future__ import annotations

import json
import re
from functools import cached_property
from pathlib import Path
from typing import Any

from ncm.aia import AiaIndex, load_aia
from ncm.parser import CATALOG_PATH, CATALOG_POC_PATH, parse_ncm, save_catalog

def _norm(code: str) -> str:
    return code.replace(" ", "")


class NcmCatalog:
    def __init__(self, data: dict[str, Any], aia: AiaIndex | None = None):
        self.data = data
        self._chapter = {c["codigo"]: c for c in data["chapters"]}
        self._by_code = {_norm(n["codigo"]): n for n in data["nodes"]}
        self.aia = aia

    @classmethod
    def from_pdf(cls) -> "NcmCatalog":
        catalog = parse_ncm()
        save_catalog(catalog, CATALOG_PATH)
        return cls(catalog, aia=load_aia())

    @classmethod
    def from_json(cls, path: Path | None = None) -> "NcmCatalog":
        if path is None:
            path = CATALOG_PATH if CATALOG_PATH.exists() else CATALOG_POC_PATH
        if not path.exists():
            return cls.from_pdf()
        return cls(json.loads(path.read_text(encoding="utf-8")), aia=load_aia())

    @property
    def rgi(self) -> str:
        return self.data["rgi"]

    @cached_property
    def chapters(self) -> list[dict[str, Any]]:
        return list(self.data["chapters"])

    def search_chapters(self, query: str) -> list[dict[str, str]]:
        """Returns catalog chapters; LLM chooses, not the score."""
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
        aia_notes = ""
        if self.aia:
            aia_notes = self.aia.chapter_notes.get(_norm(chapter).zfill(2)) or ""
        return {
            "chapter": ch["codigo"],
            "title": ch["titulo"],
            "chapter_notes": aia_notes or ch["notas"],
            "section_notes": ch.get("notas_seccion") or "",
            "subheading_notes": ch.get("notas_subpartida") or "",
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

    def list_subheadings(self, heading: str) -> list[dict[str, Any]]:
        p = _norm(heading)
        return [
            {
                "subheading": node["codigo"],
                "description": node["descripcion"],
            }
            for node in self.data["nodes"]
            if node["partida"] == p and node["nivel"] == 6
        ]

    def list_items(self, heading: str) -> list[dict[str, Any]]:
        raw = _norm(heading)
        digits = raw.replace(".", "")
        if len(digits) >= 6:
            prefix = f"{digits[:4]}.{digits[4:6]}"
            items = [
                node for node in self.data["items"] if node["codigo"].startswith(prefix)
            ]
        else:
            items = [node for node in self.data["items"] if node["partida"] == raw]
        return [self._item_card(node) for node in items]

    def get_ncm(self, code: str) -> dict[str, Any] | None:
        node = self._by_code.get(_norm(code))
        if not node or node["nivel"] != 8 or node["aec"] is None:
            return None
        return self._item_card(node)

    def _aec(self, code: str, fallback: float | None) -> float | None:
        if self.aia:
            die = self.aia.die(code)
            if die is not None:
                return die
        return fallback

    def _item_card(self, node: dict[str, Any]) -> dict[str, Any]:
        card = dict(node)
        card["aec"] = self._aec(node["codigo"], node.get("aec"))
        card["ncm"] = node["codigo"]
        card["description"] = node["descripcion"]
        card["full_description"] = node["descripcion_completa"]
        card["aec_flag"] = node.get("aec_flag")
        return card
