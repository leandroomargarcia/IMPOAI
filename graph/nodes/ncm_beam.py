"""items-beam: BM25 items + LLM heading beam, ranked finalists graded in order."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from graph.chains.ncm_agent import heading_beam_chain, rank_chain
from graph.consts import (
    BEAM_FINALISTS,
    BEAM_HEADINGS,
    BEAM_MAX_CANDIDATES,
    BEAM_NOTES_CHAPTERS,
    BEAM_TOP_ITEMS,
)
from graph.nodes.calculate_costs import strip_cif_clause
from graph.nodes.ncm_node import catalog, chapter_notes_text
from graph.state import GraphState
from ncm.item_index import ItemIndex
from ncm.thresholds import item_conflicts

RESET = {
    "ncm": "",
    "ncm_item": "",
    "ncm_heading": "",
    "ncm_subheading": "",
    "ncm_descripcion": "",
    "ncm_aec": 0.0,
    "ncm_aec_flag": "",
    "ncm_medidas": [],
    "es_valido": False,
}


@lru_cache(maxsize=1)
def item_index() -> ItemIndex:
    return ItemIndex.from_catalog(catalog)


def heading_code(raw: str) -> str:
    """'9403', '94.03' or '9403.50' -> '94.03'; '' if fewer than 4 digits."""
    d = "".join(c for c in raw or "" if c.isdigit())
    return f"{d[:2]}.{d[2:4]}" if len(d) >= 4 else ""


def item_code(raw: str) -> str:
    """'94035000' or '9403.50.00' -> '9403.50.00'; '' if not 8 digits."""
    d = "".join(c for c in raw or "" if c.isdigit())
    return f"{d[:4]}.{d[4:6]}.{d[6:8]}" if len(d) == 8 else ""


def group_candidates(items: list[dict[str, Any]]) -> str:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        groups.setdefault(item["partida"], []).append(item)
    blocks = []
    for heading, rows in groups.items():
        lines = "\n".join(
            f"- {r['ncm']} | AEC {r['aec']} | {r['full_description']}" for r in rows
        )
        blocks.append(f"## {heading}\n{lines}")
    return "\n\n".join(blocks)


def gather_candidates(state: GraphState) -> dict:
    question = state["question"]
    query = strip_cif_clause(question)
    hits = item_index().search(query, k=BEAM_TOP_ITEMS)
    beam = heading_beam_chain.invoke(
        {"beam": BEAM_HEADINGS, "question": query, "chapters": catalog.chapter_labels()}
    )
    headings: list[str] = []
    for raw in beam.headings:
        code = heading_code(raw)
        if code and code not in headings and catalog.list_items(code):
            headings.append(code)
    headings = headings[:BEAM_HEADINGS]
    print("beam headings", headings, "-", beam.motive)
    print("bm25 top", [h["ncm"] for h in hits[:5]])

    cards: dict[str, dict[str, Any]] = {}
    for hit in hits:
        card = catalog.get_ncm(hit["ncm"])
        if card:
            cards.setdefault(card["ncm"], card)
    for heading in headings:
        for card in catalog.list_items(heading):
            if card.get("aec") is not None:
                cards.setdefault(card["ncm"], card)
    pool = list(cards.values())
    candidates = [c for c in pool if not item_conflicts(question, c["full_description"])] or pool
    candidates = candidates[:BEAM_MAX_CANDIDATES]
    if not candidates:
        print("no candidates")
        return {**RESET, "ncm_ranked": [], "ncm_finalists": [], "attempts": 0}

    chapters: list[str] = []
    for chapter in [h[:2] for h in headings] + [c["capitulo"] for c in candidates]:
        if chapter not in chapters:
            chapters.append(chapter)
    notes = "\n\n".join(chapter_notes_text(c) for c in chapters[:BEAM_NOTES_CHAPTERS])

    ranking = rank_chain.invoke(
        {
            "finalists": BEAM_FINALISTS,
            "rgi": catalog.rgi,
            "question": question,
            "notes": notes,
            "candidates": group_candidates(candidates),
        }
    )
    allowed = {c["ncm"] for c in candidates}
    finalists: list[str] = []
    for raw in ranking.items:
        code = item_code(raw)
        if code in allowed and code not in finalists:
            finalists.append(code)
    finalists = finalists[:BEAM_FINALISTS] or [candidates[0]["ncm"]]
    print("candidates", len(candidates), "finalists", finalists, "-", ranking.motive)
    return {**RESET, "ncm_ranked": finalists, "ncm_finalists": finalists, "attempts": 0}


def next_finalist(state: GraphState) -> dict:
    left = list(state.get("ncm_finalists") or [])
    code = left.pop(0)
    chapter = code[:2]
    print("try", code, "left", left)
    return {
        **RESET,
        "ncm_item": code,
        "ncm_chapter": chapter,
        "ncm_heading": f"{code[:2]}.{code[2:4]}",
        "ncm_notes": chapter_notes_text(chapter),
        "ncm_finalists": left,
        "attempts": state.get("attempts", 0) + 1,
    }


def after_gather(state: GraphState) -> str:
    return "next" if state.get("ncm_finalists") else "fail"


def after_beam_fetch(state: GraphState) -> str:
    if state.get("ncm"):
        return "grade"
    return after_beam_grade(state)


def after_beam_grade(state: GraphState) -> str:
    if state.get("es_valido"):
        return "ok"
    if state.get("ncm_finalists"):
        print("next finalist")
        return "retry"
    print("FAILED: finalists exhausted")
    return "fail"