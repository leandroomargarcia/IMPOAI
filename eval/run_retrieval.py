"""Offline recall of the bottom-up item index on the gold set. No LLM calls."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.metrics import digits, pct
from graph.nodes.calculate_costs import strip_cif_clause
from ncm.catalog import NcmCatalog
from ncm.item_index import ItemIndex

GOLD_PATH = ROOT / "eval" / "gold.json"
OUT_PATH = ROOT / "eval" / "results" / "retrieval-bm25.jsonl"
KS = (5, 10, 20, 50)


def rank_of(hits: list[dict], gold: str, n: int) -> int | None:
    """1-based rank of the first hit sharing the first n gold digits."""
    target = digits(gold)[:n]
    for pos, hit in enumerate(hits, 1):
        if digits(hit["ncm"])[:n] == target:
            return pos
    return None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--gold", type=Path, default=GOLD_PATH)
    p.add_argument("--out", type=Path, default=OUT_PATH)
    p.add_argument("--id", dest="row_id", default="")
    p.add_argument("--show", type=int, default=0, help="Print top-N hits per row.")
    args = p.parse_args()

    rows = json.loads(args.gold.read_text(encoding="utf-8"))
    if args.row_id:
        rows = [r for r in rows if r["id"] == args.row_id]
    index = ItemIndex.from_catalog(NcmCatalog.from_json())

    recs = []
    for row in rows:
        query = strip_cif_clause(row["question"])
        hits = index.search(query, k=None)
        rec = {
            "id": row["id"],
            "tag": row.get("tag"),
            "query": query,
            "ncm_gold": row["ncm_gold"],
            "rank8": rank_of(hits, row["ncm_gold"], 8),
            "rank4": rank_of(hits, row["ncm_gold"], 4),
            "top5": [h["ncm"] for h in hits[:5]],
        }
        recs.append(rec)
        if args.show:
            print(f"\n{row['id']}: {query}  gold {row['ncm_gold']}  rank8 {rec['rank8']}")
            for h in hits[: args.show]:
                print(f"  {h['ncm']}  {h['score']:6.2f}  {h['text'][:110]}")

    n = len(recs)
    summary = {"n": n}
    for k in KS:
        summary[f"item@{k}"] = pct(sum(bool(r["rank8"] and r["rank8"] <= k) for r in recs), n)
        summary[f"heading@{k}"] = pct(sum(bool(r["rank4"] and r["rank4"] <= k) for r in recs), n)
    print(json.dumps(summary, indent=2))

    misses = [r for r in recs if not r["rank8"] or r["rank8"] > 20]
    print(f"\nitem not in top 20: {len(misses)}")
    for r in misses:
        print(f"  {r['id']:<18} gold {r['ncm_gold']}  rank8 {r['rank8']}  rank4 {r['rank4']}  top5 {r['top5']}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()