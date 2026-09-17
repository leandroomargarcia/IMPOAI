# 0 BOOTSTRAP
# Load secrets, the NCM catalog JSON, and the chat model.
# Used to open the office: nothing is classified here.
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from graph.state import GraphState
from graph.nodes.ncm_node import (
    pick_chapter,
    load_notes,
    choose_heading,
    after_heading,
    choose_subheading,
    choose_item,
    fetch_ncm,
    after_fetch,
    grade_ncm,
    after_grade,
    ncm_done,
)
from graph.nodes.search_price import search_price
from graph.nodes.calculate_costs import calc_duty
from graph.nodes.web_search_hab import web_search_hab
from graph.nodes.hab_agent import hab_agent
from graph.nodes.orchestrator import join_branches, orchestrator
from langfuse.langchain import CallbackHandler
from langfuse import get_client

load_dotenv()


def build_graph():
    builder = StateGraph(GraphState)
    builder.add_node("pick_chapter", pick_chapter)
    builder.add_node("load_notes", load_notes)
    builder.add_node("choose_heading", choose_heading)
    builder.add_node("choose_subheading", choose_subheading)
    builder.add_node("choose_item", choose_item)
    builder.add_node("fetch_ncm", fetch_ncm)
    builder.add_node("grade_ncm", grade_ncm)
    builder.add_node("ncm_done", ncm_done)
    builder.add_node("web_search_hab", web_search_hab)
    builder.add_node("hab_agent", hab_agent)
    builder.add_node("join", join_branches)
    builder.add_node("search_price", search_price)
    builder.add_node("calc_duty", calc_duty)
    builder.add_node("orchestrator", orchestrator)

    builder.add_edge(START, "pick_chapter")
    builder.add_edge(START, "search_price")
    builder.add_edge("web_search_hab", "hab_agent")

    builder.add_edge("pick_chapter", "load_notes")
    builder.add_edge("load_notes", "choose_heading")
    builder.add_conditional_edges(
        "choose_heading",
        after_heading,
        {"subheading": "choose_subheading", "item": "choose_item"},
    )
    builder.add_edge("choose_subheading", "choose_item")
    builder.add_edge("choose_item", "fetch_ncm")
    builder.add_conditional_edges(
        "fetch_ncm",
        after_fetch,
        {"grade": "grade_ncm", "retry": "pick_chapter", "fail": "ncm_done"},
    )
    builder.add_conditional_edges(
        "grade_ncm",
        after_grade,
        {"ok": "ncm_done", "retry": "pick_chapter", "fail": "ncm_done"},
    )

    builder.add_edge("ncm_done", "web_search_hab")
    builder.add_edge("ncm_done", "calc_duty")
    builder.add_edge(["hab_agent", "search_price", "calc_duty"], "join")
    builder.add_edge("join", "orchestrator")
    builder.add_edge("orchestrator", END)
    return builder.compile()


app = build_graph()

if __name__ == "__main__":
    langfuse_handler = CallbackHandler()
    out = app.invoke(
        {
            "question": "Caldera acuotubular de vapor 20 toneladas por hora CIF 80000 USD origen China",
            "attempts": 0,
        },
        config={"callbacks": [langfuse_handler]},
    )
    print("STATE chapter", out.get("ncm_chapter"), "attempts", out.get("attempts"))
    print("STATE heading", out.get("ncm_heading"))
    print("STATE item", out.get("ncm_item"))
    print("STATE ncm", out.get("ncm"), "AEC", out.get("ncm_aec"), "flag", out.get("ncm_aec_flag"))
    print("STATE grade", out.get("es_valido"))
    print("STATE cif", out.get("cif"))
    print("STATE duty", out.get("impuestos_estimados"))
    print("STATE sale", out.get("precio_info") or out.get("precio_ref"), out.get("ncm_currency"))
    print("STATE hab", (out.get("hab_info") or "")[:200])
    print("REPORT")
    print(out.get("reporte_final"))
    get_client().flush()
