"""
This script contains automated tests to validate the behavior of the items-beam graph,
using mocked Language Models (LLMs). It checks that the NCM classification and selection
flow works as expected in various scenarios, simulating different model responses. The tests
ensure the robustness of the tariff code selection process under different conditions.
"""

import pytest
from langgraph.graph import END, START, StateGraph

import graph.graph as graph_mod
import graph.nodes.ncm_beam as ncm_beam
import graph.nodes.ncm_node as ncm_node
from graph.nodes.ncm_beam import (
    after_beam_fetch,
    after_beam_grade,
    after_gather,
    gather_candidates,
    heading_code,
    item_code,
    next_finalist,
)
from graph.nodes.ncm_node import fetch_ncm, grade_ncm
from graph.state import GraphState


def _chain(result):
    return type("C", (), {"invoke": staticmethod(lambda _: result)})()


def _beam_app():
    g = StateGraph(GraphState)
    g.add_node("gather_candidates", gather_candidates)
    g.add_node("next_finalist", next_finalist)
    g.add_node("fetch_ncm", fetch_ncm)
    g.add_node("grade_ncm", grade_ncm)
    g.add_edge(START, "gather_candidates")
    g.add_conditional_edges("gather_candidates", after_gather, {"next": "next_finalist", "fail": END})
    g.add_edge("next_finalist", "fetch_ncm")
    g.add_conditional_edges("fetch_ncm", after_beam_fetch, {"grade": "grade_ncm", "retry": "next_finalist", "fail": END})
    g.add_conditional_edges("grade_ncm", after_beam_grade, {"ok": END, "retry": "next_finalist", "fail": END})
    return g.compile()


def test_build_graph_keeps_v1_as_default():
    assert graph_mod.NCM_METHOD == "v1-chapter-first"
    v1 = set(graph_mod.build_graph("v1-chapter-first").get_graph().nodes)
    beam = set(graph_mod.build_graph("items-beam").get_graph().nodes)
    assert {"pick_chapter", "choose_item"} <= v1
    assert not {"gather_candidates", "next_finalist"} & v1
    assert {"gather_candidates", "next_finalist"} <= beam
    assert "pick_chapter" not in beam
    with pytest.raises(ValueError):
        graph_mod.build_graph("hs6-first")


def test_codes_normalize():
    assert heading_code("9403") == "94.03"
    assert heading_code("9403.50") == "94.03"
    assert heading_code("94") == ""
    assert item_code("94035000") == "9403.50.00"
    assert item_code("9403.50") == ""


def test_beam_tries_next_finalist_after_reject(monkeypatch):
    no_hits = type("I", (), {"search": staticmethod(lambda q, k=20: [])})()
    monkeypatch.setattr(ncm_beam, "item_index", lambda: no_hits)
    monkeypatch.setattr(
        ncm_beam,
        "heading_beam_chain",
        _chain(type("R", (), {"headings": ["0101", "99.99"], "motive": "x"})()),
    )
    monkeypatch.setattr(
        ncm_beam,
        "rank_chain",
        _chain(type("R", (), {"items": ["0101.29.00", "01012100", "9999.99.99"], "motive": "x"})()),
    )
    verdicts = iter([False, True])
    monkeypatch.setattr(
        ncm_node,
        "grade_chain",
        type("C", (), {"invoke": staticmethod(
            lambda _: type("R", (), {"is_valid": next(verdicts), "motive": "x"})()
        )})(),
    )
    out = _beam_app().invoke({"question": "purebred breeding horse CIF 1000", "attempts": 0})
    assert out["ncm_ranked"] == ["0101.29.00", "0101.21.00"]
    assert out["ncm"] == "0101.21.00"
    assert out["es_valido"] is True
    assert out["attempts"] == 2
    assert out["ncm_heading"] == "01.01"