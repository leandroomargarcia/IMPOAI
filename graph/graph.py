# 0 BOOTSTRAP
# Load secrets, the NCM catalog JSON, and the chat model.
# Used to open the office: nothing is classified here.
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from graph.state import GraphState
from graph.nodes.ncm_node import(
    pick_chapter,
    load_notes,
    choose_heading,
    choose_item,
    fetch_ncm,
    grade_ncm,
    after_grade,

)

from graph.nodes.search_price import search_price
from graph.nodes.calculate_costs import calc_duty
from graph.nodes.web_search_hab import web_search_hab
from graph.nodes.hab_agent import hab_agent

load_dotenv()

builder = StateGraph(GraphState)
builder.add_node("pick_chapter", pick_chapter)
builder.add_node("load_notes", load_notes)
builder.add_node("choose_heading", choose_heading)
builder.add_node("choose_item", choose_item)
builder.add_node("fetch_ncm", fetch_ncm)
builder.add_node("grade_ncm", grade_ncm)
builder.add_node("search_price", search_price)
builder.add_node("calc_duty", calc_duty)
builder.add_node("web_search_hab", web_search_hab)
builder.add_node("hab_agent", hab_agent)
builder.add_edge(START, "pick_chapter")
builder.add_edge("pick_chapter", "load_notes")
builder.add_edge("load_notes", "choose_heading")
builder.add_edge("choose_heading", "choose_item")
builder.add_edge("choose_item", "fetch_ncm")
builder.add_edge("fetch_ncm", "grade_ncm")
builder.add_conditional_edges(
    "grade_ncm",
    after_grade,
    {"ok": "search_price", "retry": "pick_chapter", "fail": END},
)
builder.add_edge("search_price", "calc_duty")
builder.add_edge("calc_duty", "web_search_hab")
builder.add_edge("web_search_hab", "hab_agent")
builder.add_edge("hab_agent", END)

app = builder.compile()

if __name__ == "__main__":
    out = app.invoke({"question": "purebred breeding horse", "attempts": 0})
    print("STATE chapter", out.get("ncm_chapter"), "attempts", out.get("attempts"))
    print("STATE notes", (out.get("ncm_notes") or "")[:80], "...")
    print("STATE heading", out.get("ncm_heading"))
    print("STATE item", out.get("ncm_item"))
    print("STATE ncm", out.get("ncm"), "AEC", out.get("ncm_aec"))
    print("STATE grade", out.get("es_valido"))
    print("STATE price", out.get("precio_ref"), out.get("ncm_currency"))
    print("STATE duty", out.get("impuestos_estimados"))
    print("STATE hab", (out.get("hab_info") or "")[:200])