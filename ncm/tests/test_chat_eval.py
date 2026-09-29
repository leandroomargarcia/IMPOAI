import json
from collections import Counter
from pathlib import Path

from eval.chat_metrics import parse_sse, score_turn, summarize_chat
from eval.metrics import hits

GOLD = Path(__file__).resolve().parents[2] / "eval" / "chat_gold.json"
NCM_GOLD = Path(__file__).resolve().parents[2] / "eval" / "gold.json"


def test_chat_gold_sheet():
    rows = json.loads(GOLD.read_text(encoding="utf-8"))
    ids = [r["id"] for r in rows]
    assert len(ids) == 25
    assert len(ids) == len(set(ids))
    tags = Counter(r["tag"] for r in rows)
    assert tags["faq"] == 6
    assert tags["gate"] == 5
    assert tags["ready"] == 4
    assert tags["seq"] == 4
    assert tags["jail"] == 2
    assert tags["integrate"] == 4
    office = {r["id"]: r["ncm_gold"] for r in json.loads(NCM_GOLD.read_text(encoding="utf-8"))}
    for row in rows:
        assert row["turns"]
        assert row["tag"]
        if row.get("live"):
            assert row["tag"] == "integrate"
            gold = row["turns"][0]["expect"]["ncm_gold"]
            assert gold in office.values()


def test_score_faq_forbids_invented_ncm():
    ok = score_turn(
        {"tool": False, "forbid_ncm": True},
        tokens="La tasa de estadística es un tributo aduanero.",
        card=None,
    )
    assert ok["chat_turn_ok"] is True
    bad = score_turn(
        {"tool": False, "forbid_ncm": True},
        tokens="Sería 8402.12.00.",
        card=None,
    )
    assert bad["chat_no_invented_ncm"] is False
    assert bad["chat_turn_ok"] is False


def test_score_cif_gate_and_tool():
    gate = score_turn(
        {"tool": False, "ask_cif": True},
        tokens="Pasame el CIF en USD de esta mercadería.",
        card=None,
    )
    assert gate["chat_cif_gate"] is True
    assert gate["chat_ask_cif"] is True
    leaked = score_turn(
        {"tool": False, "ask_cif": True},
        tokens="Listo.",
        card={"ncm": "8402.12.00"},
    )
    assert leaked["chat_tool_ok"] is False
    assert leaked["chat_cif_gate"] is False


def test_score_faithful_wrap_and_hit8():
    tokens = "Listo. NCM 0901.11.10: En grano; partida: Café."
    rec = score_turn(
        {"tool": True, "ncm_gold": "0901.11.10"},
        tokens=tokens,
        card={"ncm": "0901.11.10"},
    )
    assert rec["chat_faithful_wrap"] is True
    assert rec["hit8"] is True
    assert rec["chat_turn_ok"] is True
    assert hits("0901.11.10", "0901.11.10")["hit8"] is True


def test_parse_sse_and_summarize():
    body = (
        'event: token\ndata: "Pasame el CIF"\n\n'
        'event: status\ndata: "done"\n\n'
    )
    parsed = parse_sse(body)
    assert "CIF" in parsed["tokens"]
    assert parsed["card"] is None
    recs = [
        {
            "id": "a",
            "tag": "gate",
            "want_tool": False,
            "used_tool": False,
            "chat_tool_ok": True,
            "chat_cif_gate": True,
            "chat_turn_ok": True,
            "wall_s": 1.0,
        },
        {
            "id": "b",
            "tag": "ready",
            "want_tool": True,
            "used_tool": True,
            "chat_tool_ok": True,
            "chat_faithful_wrap": True,
            "chat_turn_ok": True,
            "wall_s": 2.0,
        },
    ]
    s = summarize_chat(recs)
    assert s["n"] == 2
    assert s["dialogues"] == 2
    assert s["routing"]["tool_precision"] == 100.0
    assert s["routing"]["cif_gate"] == 100.0
    assert s["by_tag"]["gate"]["n"] == 1
