from graph.state import GraphState
from ncm.catalog import NcmCatalog
from graph.chains.ncm_agent import router, heading_chain, item_chain, grade_chain
from graph.consts import MAX_ATTEMPTS

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
    return {"ncm_heading": heading.heading}

def choose_item(state: GraphState) -> dict:
    items = catalog.list_items(state["ncm_heading"])
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
        return {"es_valido": False}
    print("card OK", card["codigo"], "AEC", card["aec"])
    print(card["descripcion_completa"])
    return {
        "ncm": card["codigo"],
        "ncm_aec": card["aec"],
        "ncm_descripcion": card["descripcion_completa"],
    }

def grade_ncm(state: GraphState) -> dict:
    if not state.get("ncm"):
        print("no card, skip grade")
        return {"es_valido": False}
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
    return {"es_valido": grade.is_valid}

def after_grade(state: GraphState) -> str:
    if state.get("es_valido"):
        return "ok"
    if state.get("attempts", 0) < MAX_ATTEMPTS:
        print("retry")
        return "retry"
    print("FAILED after 3 attempts")
    return "fail"