"""Live gold job for NCM v1. Not part of default pytest (calls OpenAI + Tavily)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.metrics import hits, summarize

GOLD_PATH = ROOT / "eval" / "gold.json"
RESULTS_DIR = ROOT / "eval" / "results"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=1)
    p.add_argument("--id", dest="row_id", default="")
    p.add_argument("--gold", type=Path, default=GOLD_PATH)
    p.add_argument("--out", type=Path, default=RESULTS_DIR / "v1.jsonl")
    p.add_argument(
        "--from-jsonl",
        type=Path,
        default=None,
        help="Score an existing jsonl; do not call the graph.",
    )
    return p.parse_args()


def write_summary(recs: list[dict], jsonl_path: Path) -> dict:
    summary = summarize(recs)
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    print(text)
    dest = jsonl_path.with_suffix(".summary.json")
    dest.write_text(text + "\n", encoding="utf-8")
    print("wrote", dest)
    return summary


def load_jsonl(path: Path) -> list[dict]:
    recs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            recs.append(json.loads(line))
    return recs


def run_graph(rows: list[dict], out_path: Path) -> list[dict]:
    from dotenv import load_dotenv
    from langfuse import get_client
    from langfuse.langchain import CallbackHandler

    from graph.graph import app

    load_dotenv()
    lf = get_client()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    recs: list[dict] = []
    with out_path.open("a", encoding="utf-8") as fh:
        for row in rows:
            tag = row.get("tag") or "untagged"
            trace_id = lf.create_trace_id()
            handler = CallbackHandler(trace_context={"trace_id": trace_id})
            t0 = time.perf_counter()
            out = app.invoke(
                {"question": row["question"], "attempts": 0},
                config={
                    "callbacks": [handler],
                    "metadata": {
                        "langfuse_trace_name": row["id"],
                        "langfuse_tags": ["gold", "v1", tag],
                        "gold_id": row["id"],
                        "ncm_gold": row["ncm_gold"],
                    },
                },
            )
            wall = round(time.perf_counter() - t0, 3)
            lf.flush()
            pred = out.get("ncm") or ""
            score = hits(pred, row["ncm_gold"])
            for name in ("hit2", "hit4", "hit6", "hit8"):
                lf.create_score(
                    name=name,
                    value=1.0 if score[name] else 0.0,
                    trace_id=trace_id,
                    data_type="BOOLEAN",
                    comment=f"gold={row['ncm_gold']} pred={pred or '-'}",
                    metadata={"gold_id": row["id"], "tag": tag},
                )
            lf.create_score(
                name="wall_s",
                value=wall,
                trace_id=trace_id,
                data_type="NUMERIC",
            )
            lf.flush()
            rec = {
                "id": row["id"],
                "tag": row.get("tag"),
                "ncm_gold": row["ncm_gold"],
                "ncm_pred": pred,
                "chapter": out.get("ncm_chapter"),
                "heading": out.get("ncm_heading"),
                "attempts": out.get("attempts"),
                "grade": out.get("es_valido"),
                "wall_s": wall,
                "trace_id": trace_id,
                **score,
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            recs.append(rec)
            print(
                rec["id"],
                "gold",
                rec["ncm_gold"],
                "pred",
                pred or "-",
                "hit8",
                rec["hit8"],
                "wall",
                wall,
                flush=True,
            )
    return recs

def main() -> None:
    args = parse_args()
    if args.from_jsonl:
        recs = load_jsonl(args.from_jsonl)
        write_summary(recs, args.from_jsonl)
        return

    rows = json.loads(args.gold.read_text(encoding="utf-8"))
    if args.row_id:
        rows = [r for r in rows if r["id"] == args.row_id]
        if not rows:
            raise SystemExit(f"unknown id: {args.row_id}")
    rows = rows[: args.limit]
    run_graph(rows, args.out)
    write_summary(load_jsonl(args.out), args.out)


if __name__ == "__main__":
    main()
