from graph.state import GraphState
from ncm.catalog import NcmCatalog
from graph.chains.ncm_agent import (
    router,
    heading_chain,
    subheading_chain,
    item_chain,
    grade_chain,
)
from graph.consts import ITEM_LIST_LIMIT, MAX_ATTEMPTS
from ncm.thresholds import filter_items, item_conflicts

catalog = NcmCatalog.from_json()


def pick_chapter(state: GraphState) -> dict:
    question = state["question"]
    caps = catalog.search_chapters(question)
    list_caps = "\n".join(f"- {c['chapter']}: {c['title']}" for c in caps)
    cap = router.invoke({"rgi": catalog.rgi, "question": question, "chapters": list_caps})
    print("chapter", cap.chapter, "-", cap.motive)
    return {
        "ncm_chapter": cap.chapter.zfill(2),
        "attempts": state.get("attempts", 0) + 1,
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


def load_notes(state: GraphState) -> dict:
    notes = catalog.get_notes(state["ncm_chapter"])
    notes_text = (
        f"{notes['title']}\n"
        f"{notes['chapter_notes']}\n"
        f"{notes['section_notes']}\n"
        f"{notes.get('subheading_notes') or ''}"
    )
    print("notes loaded")
    print(notes_text)
    return {"ncm_notes": notes_text}


def choose_heading(state: GraphState) -> dict:
    headings = catalog.list_headings(state["ncm_chapter"])
    list_headings = "\n".join(
        f"- {h['heading']}: {h['description']}" for h in headings
    )
    heading = heading_chain.invoke(
        {
            "rgi": catalog.rgi,
            "question": state["question"],
            "notes": state["ncm_notes"],
            "headings": list_headings,
        }
    )
    print("heading", heading.heading, "-", heading.motive)
    return {"ncm_heading": heading.heading, "ncm_subheading": ""}


def after_heading(state: GraphState) -> str:
    heading = state["ncm_heading"]
    items = catalog.list_items(heading)
    subs = catalog.list_subheadings(heading)
    if len(items) > ITEM_LIST_LIMIT and subs:
        return "subheading"
    return "item"


def choose_subheading(state: GraphState) -> dict:
    subs = catalog.list_subheadings(state["ncm_heading"])
    list_subs = "\n".join(
        f"- {s['subheading']}: {s['description']}" for s in subs
    )
    choice = subheading_chain.invoke(
        {
            "rgi": catalog.rgi,
            "question": state["question"],
            "notes": state["ncm_notes"],
            "subheadings": list_subs,
        }
    )
    print("subheading", choice.subheading, "-", choice.motive)
    return {"ncm_subheading": choice.subheading}


def choose_item(state: GraphState) -> dict:
    key = state.get("ncm_subheading") or state["ncm_heading"]
    items = catalog.list_items(key)
    filtered = filter_items(state.get("question") or "", items)
    if len(filtered) < len(items):
        print(
            "NCM umbral",
            len(items),
            "->",
            len(filtered),
            [i.get("ncm") for i in filtered],
        )
    items = filtered
    if len(items) == 1 and items[0].get("ncm"):
        code = items[0]["ncm"]
        print("item", code, "- único candidato tras umbral")
        return {"ncm_item": code}
    list_items = "\n".join(
        f"- {i['ncm']} | AEC {i['aec']} | {i['full_description']}" for i in items
    )
    item = item_chain.invoke(
        {
            "rgi": catalog.rgi,
            "question": state["question"],
            "notes": state["ncm_notes"],
            "items": list_items,
        }
    )
    print("item", item.item, "-", item.motive)
    return {"ncm_item": item.item}


def fetch_ncm(state: GraphState) -> dict:
    card = catalog.get_ncm(state["ncm_item"])
    if not card:
        print("code not in catalog:", state["ncm_item"])
        return {
            "es_valido": False,
            "ncm": "",
            "ncm_aec": 0.0,
            "ncm_aec_flag": "",
            "ncm_descripcion": "",
            "ncm_medidas": [],
        }
    medidas = card.get("medidas") or []
    flag = card.get("aec_flag") or ""
    print("card OK", card["codigo"], "AEC", card["aec"], flag or "-",
          "AIA" if catalog.aia and catalog.aia.die(card["codigo"]) is not None else "NCM",
          "medidas", len(medidas))
    print(card["descripcion_completa"])
    return {
        "ncm": card["codigo"],
        "ncm_aec": card["aec"],
        "ncm_aec_flag": flag,
        "ncm_descripcion": card["descripcion_completa"],
        "ncm_medidas": medidas,
    }


def after_fetch(state: GraphState) -> str:
    if state.get("ncm"):
        return "grade"
    return after_grade(state)


def grade_ncm(state: GraphState) -> dict:
    if not state.get("ncm"):
        print("no card, skip grade")
        return {"es_valido": False, "ncm_feedback": "code not in catalog"}
    if item_conflicts(state.get("question") or "", state.get("ncm_descripcion") or ""):
        print("rejected: umbral numérico")
        return {
            "es_valido": False,
            "ncm_feedback": "el ítem no cubre el umbral numérico de la pregunta",
        }
    grade = grade_chain.invoke(
        {
            "rgi": catalog.rgi,
            "question": state["question"],
            "notes": state["ncm_notes"],
            "item": state["ncm_item"],
            "card": f"{state['ncm']} | {state['ncm_descripcion']}",
        }
    )
    if grade.is_valid:
        print("DONE", state["ncm"], "AEC", state["ncm_aec"])
    else:
        print("rejected:", grade.motive)
    return {"es_valido": grade.is_valid, "ncm_feedback": grade.motive}


def after_grade(state: GraphState) -> str:
    if state.get("es_valido"):
        return "ok"
    if state.get("attempts", 0) < MAX_ATTEMPTS:
        print("retry")
        return "retry"
    print("FAILED after 3 attempts")
    return "fail"


def ncm_done(state: GraphState) -> dict:
    if state.get("es_valido") and state.get("ncm"):
        info = (
            f"{state['ncm']} | {state.get('ncm_descripcion')} | "
            f"AEC {state.get('ncm_aec')}"
            + (f" {state['ncm_aec_flag']}" if state.get("ncm_aec_flag") else "")
        )
        print("NCM done", info)
        return {"ncm_info": info}
    feedback = state.get("ncm_feedback") or ""
    info = "No se pudo clasificar el NCM (presupuesto de intentos agotado)."
    if feedback:
        info = f"{info} {feedback}"
    print("NCM fail", info)
    return {"ncm_info": info, "es_valido": False}
