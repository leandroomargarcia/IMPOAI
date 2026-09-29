"""Chat-gold scoring. Routing and CIF hygiene, not office hit8 (except integrate)."""

from __future__ import annotations

import json
import re
from collections import defaultdict

from eval.metrics import digits, hits, pct, percentile

NCM_RE = re.compile(r"\b\d{4}\.\d{2}\.\d{2}\b")
CIF_ASK_RE = re.compile(r"\bcif\b", re.I)

SCORE_NAMES = (
    "chat_tool_ok",
    "chat_ask_cif",
    "chat_cif_gate",
    "chat_no_invented_ncm",
    "chat_faithful_wrap",
    "chat_turn_ok",
)


def parse_sse(body: str) -> dict:
    tokens: list[str] = []
    card = None
    error = None
    for block in (body or "").split("\n\n"):
        if not block.strip():
            continue
        event = "message"
        data_lines = []
        for line in block.split("\n"):
            if line.startswith("event: "):
                event = line[7:].strip()
            if line.startswith("data: "):
                data_lines.append(line[6:])
        if not data_lines:
            continue
        data = json.loads("\n".join(data_lines))
        if event == "token":
            tokens.append(data if isinstance(data, str) else str(data))
        elif event == "card":
            card = data
        elif event == "error":
            error = data
    return {"tokens": "".join(tokens), "card": card, "error": error}


def score_turn(expect: dict, *, tokens: str, card: dict | None) -> dict:
    """Deterministic checks for one user turn."""
    used_tool = card is not None
    want_tool = bool(expect.get("tool"))
    text = tokens or ""
    out: dict = {
        "used_tool": used_tool,
        "want_tool": want_tool,
        "chat_tool_ok": used_tool == want_tool,
    }
    if expect.get("ask_cif"):
        out["chat_ask_cif"] = (not used_tool) and bool(CIF_ASK_RE.search(text))
        out["chat_cif_gate"] = not used_tool
    if expect.get("forbid_ncm"):
        out["chat_no_invented_ncm"] = not bool(NCM_RE.search(text))
    must = expect.get("must") or []
    if must:
        low = text.lower()
        out["relevance"] = all(str(m).lower() in low for m in must)
    if used_tool and card:
        ncm = str(card.get("ncm") or "")
        out["ncm_pred"] = ncm
        out["chat_faithful_wrap"] = bool(ncm) and (
            ncm in text or digits(ncm)[:8] in digits(text)
        )
        gold = expect.get("ncm_gold")
        if gold:
            out["ncm_gold"] = gold
            out.update(hits(ncm, gold))
    checks = [out["chat_tool_ok"]]
    for key in (
        "chat_ask_cif",
        "chat_cif_gate",
        "chat_no_invented_ncm",
        "chat_faithful_wrap",
        "relevance",
        "hit8",
    ):
        if key in out:
            checks.append(bool(out[key]))
    out["chat_turn_ok"] = all(checks)
    return out


def langfuse_scores(turn: dict) -> list[tuple[str, float, str]]:
    """(name, 0/1, BOOLEAN) for scores present on this turn."""
    rows = []
    for name in SCORE_NAMES:
        if name in turn:
            rows.append((name, 1.0 if turn[name] else 0.0, "BOOLEAN"))
    if "hit8" in turn:
        rows.append(("hit8", 1.0 if turn["hit8"] else 0.0, "BOOLEAN"))
    if turn.get("wall_s") is not None:
        rows.append(("chat_wall_s", float(turn["wall_s"]), "NUMERIC"))
    return rows


def _rate(recs: list[dict], key: str) -> float:
    xs = [r for r in recs if key in r]
    return pct(sum(bool(r.get(key)) for r in xs), len(xs))


def _block(group: list[dict]) -> dict:
    want = [r for r in group if r.get("want_tool")]
    used = [r for r in group if r.get("used_tool")]
    tp = sum(1 for r in group if r.get("used_tool") and r.get("want_tool"))
    return {
        "n": len(group),
        "turn_ok": _rate(group, "chat_turn_ok"),
        "tool_ok": _rate(group, "chat_tool_ok"),
        "tool_precision": pct(tp, len(used)),
        "tool_recall": pct(tp, len(want)),
        "cif_gate": _rate(group, "chat_cif_gate"),
        "no_invented_ncm": _rate(group, "chat_no_invented_ncm"),
        "faithful_wrap": _rate(group, "chat_faithful_wrap"),
        "hit8": _rate(group, "hit8"),
    }


def summarize_chat(recs: list[dict]) -> dict:
    n = len(recs)
    walls = [float(r["wall_s"]) for r in recs if r.get("wall_s") is not None]
    by_tag: dict[str, list] = defaultdict(list)
    for r in recs:
        by_tag[str(r.get("tag") or "untagged")].append(r)
    return {
        "n": n,
        "dialogues": len({r.get("id") for r in recs}),
        "routing": _block(recs),
        "by_tag": {t: _block(g) for t, g in sorted(by_tag.items())},
        "latency_s": {
            "p50": percentile(walls, 50),
            "p95": percentile(walls, 95),
            "max": max(walls) if walls else None,
        },
    }
