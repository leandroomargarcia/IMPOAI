"""Parser del PDF NCM: RGI + 97 capítulos (Mercosur 2017 / AEC)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from pypdf import PdfReader

POC_CHAPTERS = {1, 9}
PDF_PATH = Path(__file__).resolve().parent.parent / "nomenclatura_comun_del_mercosur_ncm.pdf"
DATA_DIR = Path(__file__).resolve().parent / "data"
CATALOG_POC_PATH = DATA_DIR / "catalog_poc.json"
CATALOG_PATH = DATA_DIR / "catalog.json"

PAGE_NOISE = re.compile(
    r"Arancel Externo Común \(NCM 2017\)\s*|ANEXO I\s*|NCM DESCRIPCIÓN AEC RE\s*",
    re.I,
)
CHAPTER_RE = re.compile(r"^Capítulo\s+(\d+)\s*$", re.M)
SECTION_RE = re.compile(
    r"Sección\s+([IVX]+)\s*\n+(?P<title>[A-ZÁÉÍÓÚÑÜ ;,\n]+?)\n+Notas?\.\s*(?P<notes>.*)",
    re.S,
)
SUBHEADING_NOTES_RE = re.compile(r"^Notas? de subpartida\.\s*$", re.I)
CODE_RE = re.compile(
    r"^(?P<code>\d{2}\.\d{2}|\d{4}\.\d{2}(?:\.\d{1,2})?)\s+(?P<rest>.*)$"
)
DASH_RE = re.compile(r"^(?P<dashes>(?:-\s*)+)(?P<text>\S.*)$")
# AEC sits at the end of the line. Flags BK / BIT are optional.
# Greedy desc so a number in the text ("45 t por hora  14 BK 8,00") is not the AEC.
AEC_RE = re.compile(
    r"^(?P<desc>.*)\s+(?P<aec>\d+)(?:\s+(?P<flag>BK|BIT))?\s+(?P<re>\d+,\d{2})\s*$"
)
RGI_RE = re.compile(
    r"(REGLAS GENERALES PARA LA INTERPRETACIÓN.*?"
    r"seguirán el régimen de clasificación de las mercancías\.)",
    re.S,
)
AERO_RE = re.compile(
    r"REGLA DE TRIBUTACIÓN\s+PARA PRODUCTOS DEL SECTOR AERONÁUTICO.*?(?=Sección\s+I\b)",
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


def _strip_aero(text: str) -> str:
    return AERO_RE.sub("", text)


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
        prefix = text[max(0, match.start() - 6000) : match.start()]
        section_notes = ""
        sec = SECTION_RE.search(prefix)
        if sec:
            section_notes = _clean_ws(sec.group("notes").replace("________", ""))
        yield num, body, section_notes


def _split_notes_and_table(body: str) -> tuple[str, str, str, str]:
    lines = [ln.rstrip() for ln in body.splitlines()]
    title_parts: list[str] = []
    i = 0
    while i < len(lines) and not re.match(r"^Notas?\.", lines[i].strip()):
        if lines[i].strip() and lines[i].strip() != "________":
            title_parts.append(lines[i].strip())
        i += 1
    title = _clean_ws(" ".join(title_parts))

    chapter_parts: list[str] = []
    sub_parts: list[str] = []
    in_sub = False
    if i < len(lines) and re.match(r"^Notas?\.", lines[i].strip()):
        i += 1
        while i < len(lines) and lines[i].strip() != "________":
            if CODE_RE.match(lines[i].strip()):
                break
            if SUBHEADING_NOTES_RE.match(lines[i].strip()):
                in_sub = True
                i += 1
                continue
            (sub_parts if in_sub else chapter_parts).append(lines[i])
            i += 1
    notes = _clean_ws("\n".join(chapter_parts))
    sub_notes = _clean_ws("\n".join(sub_parts))
    table = "\n".join(lines[i:])
    return title, notes, sub_notes, table


def _strip_aec(text: str) -> tuple[str, int | None, str | None, str | None]:
    match = AEC_RE.match(_clean_ws(text))
    if not match:
        return _clean_ws(text), None, None, None
    return (
        _clean_ws(match.group("desc")),
        int(match.group("aec")),
        match.group("re"),
        match.group("flag"),
    )


def _parse_table(table: str, capitulo: str) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    partida_desc = ""
    last_partida = ""
    groups: list[tuple[int, str]] = []

    def set_group(depth: int, text: str) -> None:
        nonlocal groups
        label, _, _, _ = _strip_aec(text)
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
        nonlocal current, partida_desc, groups, last_partida
        if not current:
            return
        desc, aec, re_val, flag = _strip_aec(current["descripcion"])
        current["descripcion"] = desc
        current["aec"] = aec
        current["re"] = re_val
        current["aec_flag"] = flag
        partida = current["partida"]
        is_heading = current["nivel"] == 4 or (
            current["nivel"] == 6
            and current["codigo"].endswith(".00")
            and aec is None
        )
        if partida != last_partida:
            groups = []
            last_partida = partida
            partida_desc = desc if is_heading else ""
        elif is_heading:
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
                "aec_flag": None,
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


def parse_ncm(
    pdf_path: Path = PDF_PATH,
    chapters: set[int] | None = None,
    text: str | None = None,
) -> dict[str, Any]:
    """Parse the NCM PDF. `chapters=None` means every chapter in the file."""
    if text is None:
        text = _strip_aero(extract_pdf_text(pdf_path))
    catalog: dict[str, Any] = {
        "source": str(pdf_path.name),
        "rgi": _extract_rgi(text),
        "chapters": [],
        "items": [],
        "nodes": [],
    }

    for num, body, section_notes in _chapter_slices(text):
        if chapters is not None and num not in chapters:
            continue
        cap_code = f"{num:02d}"
        title, notes, sub_notes, table = _split_notes_and_table(body)
        nodes = _parse_table(table, cap_code)
        catalog["chapters"].append(
            {
                "codigo": cap_code,
                "titulo": title,
                "notas": notes,
                "notas_seccion": section_notes,
                "notas_subpartida": sub_notes,
            }
        )
        catalog["nodes"].extend(nodes)
        catalog["items"].extend(
            [n for n in nodes if n["nivel"] == 8 and n["aec"] is not None]
        )
    return catalog


def parse_poc(pdf_path: Path = PDF_PATH, chapters: set[int] | None = None) -> dict[str, Any]:
    return parse_ncm(pdf_path, chapters=chapters or POC_CHAPTERS)


def save_catalog(catalog: dict[str, Any], path: Path = CATALOG_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    raw = _strip_aero(extract_pdf_text(PDF_PATH))
    data = parse_ncm(text=raw)
    out = save_catalog(data, CATALOG_PATH)
    save_catalog(parse_ncm(text=raw, chapters=POC_CHAPTERS), CATALOG_POC_PATH)
    print(
        f"capitulos={len(data['chapters'])} "
        f"nodos={len(data['nodes'])} "
        f"items={len(data['items'])} -> {out}"
    )
