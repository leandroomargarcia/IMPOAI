"""Parser acotado del PDF NCM: RGI + capítulos de la prueba (1 y 9)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from pypdf import PdfReader

POC_CHAPTERS = {1, 9}
PDF_PATH = Path(__file__).resolve().parent.parent / "nomenclatura_comun_del_mercosur_ncm.pdf"
CATALOG_PATH = Path(__file__).resolve().parent / "data" / "catalog_poc.json"

PAGE_NOISE = re.compile(
    r"Arancel Externo Común \(NCM 2017\)\s*|ANEXO I\s*|NCM DESCRIPCIÓN AEC RE\s*",
    re.I,
)
CHAPTER_RE = re.compile(r"^Capítulo\s+(\d+)\s*$", re.M)
SECTION_RE = re.compile(
    r"Sección\s+([IVX]+)\s*\n+(?P<title>[A-ZÁÉÍÓÚÑÜ ;,\n]+?)\n+Notas?\.\s*(?P<notes>.*)",
    re.S,
)
CODE_RE = re.compile(
    r"^(?P<code>\d{2}\.\d{2}|\d{4}\.\d{2}(?:\.\d{1,2})?)\s+(?P<rest>.*)$"
)
DASH_RE = re.compile(r"^(?P<dashes>(?:-\s*)+)(?P<text>\S.*)$")
AEC_RE = re.compile(r"^(?P<desc>.*?)\s+(?P<aec>\d+)\s+(?P<re>\d+,\d{2})\s*$")
RGI_RE = re.compile(
    r"(REGLAS GENERALES PARA LA INTERPRETACIÓN.*?"
    r"seguirán el régimen de clasificación de las mercancías\.)",
    re.S,
)


def _digits(code: str) -> str:
    return code.replace(".", "")


def _nivel(code: str) -> int:
    return len(_digits(code))


def _capitulo_of(code: str) -> str:
    return _digits(code)[:2]


def _partida_of(code: str) -> str:
    d = _digits(code)[:4]
    return f"{d[:2]}.{d[2:]}"


def extract_pdf_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    chunks = []
    for page in reader.pages:
        raw = page.extract_text() or ""
        chunks.append(PAGE_NOISE.sub("", raw))
    return "\n".join(chunks)


def _clean_ws(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()


def _extract_rgi(text: str) -> str:
    match = RGI_RE.search(text)
    if not match:
        raise ValueError("No se encontraron las RGI en el PDF")
    return _clean_ws(match.group(1))


def _chapter_slices(text: str) -> Iterable[tuple[int, str, str]]:
    matches = list(CHAPTER_RE.finditer(text))
    for i, match in enumerate(matches):
        num = int(match.group(1))
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[match.end() : end]
        prefix = text[max(0, match.start() - 1800) : match.start()]
        section_notes = ""
        sec = SECTION_RE.search(prefix)
        if sec:
            section_notes = _clean_ws(sec.group("notes").replace("________", ""))
        yield num, body, section_notes


def _split_notes_and_table(body: str) -> tuple[str, str, str]:
    lines = [ln.rstrip() for ln in body.splitlines()]
    title_parts: list[str] = []
    i = 0
    while i < len(lines) and not re.match(r"^Notas?\.", lines[i].strip()):
        if lines[i].strip() and lines[i].strip() != "________":
            title_parts.append(lines[i].strip())
        i += 1
    title = _clean_ws(" ".join(title_parts))

    notes_parts: list[str] = []
    if i < len(lines) and re.match(r"^Notas?\.", lines[i].strip()):
        i += 1
        while i < len(lines) and lines[i].strip() != "________":
            if CODE_RE.match(lines[i].strip()):
                break
            notes_parts.append(lines[i])
            i += 1
    notes = _clean_ws("\n".join(notes_parts))
    table = "\n".join(lines[i:])
    return title, notes, table


def _strip_aec(text: str) -> tuple[str, int | None, str | None]:
    match = AEC_RE.match(_clean_ws(text))
    if not match:
        return _clean_ws(text), None, None
    return (
        _clean_ws(match.group("desc")),
        int(match.group("aec")),
        match.group("re"),
    )


def _parse_table(table: str, capitulo: str) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    partida_desc = ""
    groups: list[tuple[int, str]] = []

    def set_group(depth: int, text: str) -> None:
        nonlocal groups
        label, _, _ = _strip_aec(text)
        groups = [(d, t) for d, t in groups if d < depth]
        groups.append((depth, label.rstrip(":")))

    def attach_path(node: dict[str, Any]) -> None:
        parts = [partida_desc] if partida_desc else []
        parts.extend(t for _, t in groups)
        item_plain = re.sub(r"^[\-\s]+", "", node["descripcion"])
        if item_plain and item_plain not in parts:
            parts.append(item_plain)
        node["descripcion_completa"] = _clean_ws(" / ".join(p for p in parts if p))

    def flush() -> None:
        nonlocal current, partida_desc, groups
        if not current:
            return
        desc, aec, re_val = _strip_aec(current["descripcion"])
        current["descripcion"] = desc
        current["aec"] = aec
        current["re"] = re_val
        if current["nivel"] == 4 or (
            current["nivel"] == 6
            and current["codigo"].endswith(".00")
            and aec is None
        ):
            partida_desc = desc
            groups = []
        attach_path(current)
        nodes.append(current)
        current = None

    for raw in table.splitlines():
        line = raw.strip()
        if not line or line == "________":
            continue

        dash = DASH_RE.match(line)
        code = CODE_RE.match(line)

        if dash and not code:
            flush()
            set_group(dash.group("dashes").count("-"), dash.group("text"))
            continue

        if code:
            flush()
            rest = code.group("rest").strip()
            ncode = code.group("code")
            current = {
                "codigo": ncode,
                "nivel": _nivel(ncode),
                "capitulo": capitulo,
                "partida": _partida_of(ncode),
                "descripcion": rest,
                "aec": None,
                "re": None,
            }
            rest_dash = DASH_RE.match(rest)
            if rest_dash:
                set_group(rest_dash.group("dashes").count("-"), rest_dash.group("text"))
            continue

        if current is None:
            continue
        current["descripcion"] = f"{current['descripcion']} {line}"

    flush()
    return nodes


def parse_poc(pdf_path: Path = PDF_PATH, chapters: set[int] | None = None) -> dict[str, Any]:
    chapters = chapters or POC_CHAPTERS
    text = extract_pdf_text(pdf_path)
    catalog: dict[str, Any] = {
        "source": str(pdf_path.name),
        "rgi": _extract_rgi(text),
        "chapters": [],
        "items": [],
        "nodes": [],
    }

    for num, body, section_notes in _chapter_slices(text):
        if num not in chapters:
            continue
        cap_code = f"{num:02d}"
        title, notes, table = _split_notes_and_table(body)
        nodes = _parse_table(table, cap_code)
        catalog["chapters"].append(
            {
                "codigo": cap_code,
                "titulo": title,
                "notas": notes,
                "notas_seccion": section_notes,
            }
        )
        catalog["nodes"].extend(nodes)
        catalog["items"].extend(
            [n for n in nodes if n["nivel"] == 8 and n["aec"] is not None]
        )
    return catalog


def save_catalog(catalog: dict[str, Any], path: Path = CATALOG_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    data = parse_poc()
    out = save_catalog(data)
    print(
        f"capitulos={len(data['chapters'])} "
        f"nodos={len(data['nodes'])} "
        f"items={len(data['items'])} -> {out}"
    )
