"""Gold-set scoring for NCM v1. One gold code and one prediction per row."""

from __future__ import annotations

from collections import defaultdict


def digits(code: str) -> str:
    return (code or "").replace(".", "").replace(" ", "")[:8]


def hits(pred: str, gold: str) -> dict[str, bool]:
    p, g = digits(pred), digits(gold)
    return {
        "hit2": len(p) >= 2 and len(g) >= 2 and p[:2] == g[:2],
        "hit4": len(p) >= 4 and len(g) >= 4 and p[:4] == g[:4],
        "hit6": len(p) >= 6 and len(g) >= 6 and p[:6] == g[:6],
        "hit8": len(g) == 8 and p == g,
    }


def pct(num: int, den: int) -> float:
    return round(100 * num / den, 1) if den else 0.0


def percentile(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    ys = sorted(xs)
    i = min(len(ys) - 1, round((p / 100) * (len(ys) - 1)))
    return ys[i]


def _block(group: list[dict]) -> dict:
    m = len(group)
    return {
        "n": m,
        "hit2": pct(sum(bool(r.get("hit2")) for r in group), m),
        "hit4": pct(sum(bool(r.get("hit4")) for r in group), m),
        "hit6": pct(sum(bool(r.get("hit6")) for r in group), m),
        "hit8": pct(sum(bool(r.get("hit8")) for r in group), m),
    }


def summarize(recs: list[dict]) -> dict:
    """v1 score: hit8 is correctness. precision8 ≈ recall8 unless ncm_pred is empty."""
    n = len(recs)
    walls = [float(r["wall_s"]) for r in recs if r.get("wall_s") is not None]
    answered = [r for r in recs if r.get("ncm_pred")]
    by_tag: dict[str, list] = defaultdict(list)
    for r in recs:
        by_tag[str(r.get("tag") or "untagged")].append(r)
    hit8 = sum(bool(r.get("hit8")) for r in recs)
    return {
        "n": n,
        "accuracy": _block(recs),
        "precision8": pct(hit8, len(answered)),
        "recall8": pct(hit8, n),
        "by_tag": {t: _block(g) for t, g in sorted(by_tag.items())},
        "latency_s": {
            "p50": percentile(walls, 50),
            "p95": percentile(walls, 95),
            "max": max(walls) if walls else None,
        },
        "fail_grade": sum(1 for r in recs if not r.get("grade")),
        "retries": sum(1 for r in recs if (r.get("attempts") or 0) > 1),
    }
