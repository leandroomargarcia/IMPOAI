"""Live NCM gold job. Not part of default pytest (calls OpenAI + Tavily).

Each run is tagged with `--method` so classifier experiments stay apart in Langfuse.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.metrics import hits, summarize

GOLD_PATH = ROOT / "eval" / "gold.json"
RESULTS_DIR = ROOT / "eval" / "results"
DEFAULT_METHOD = "v1-chapter-first"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=1)
    p.add_argument("--id", dest="row_id", default="")
    p.add_argument("--gold", type=Path, default=GOLD_PATH)
    p.add_argument(
        "--method",
        default=DEFAULT_METHOD,
        help="Classifier under test, e.g. v1-chapter-first, items-beam, hs6-first.",
    )
    p.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Method parameter recorded in metadata (repeatable), e.g. beam=3.",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Default: eval/results/<method>.jsonl",
    )
    p.add_argument(
        "--from-jsonl",
        type=Path,
        default=None,
        help="Score an existing jsonl; do not call the graph.",
    )
    return p.parse_args()


def parse_params(pairs: list[str]) -> dict[str, str]:
    params = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key.strip():
            raise SystemExit(f"--param must be KEY=VALUE, got: {pair}")
        params[key.strip()] = value.strip()
    return params


def git_info() -> dict[str, str]:
    def run(*cmd: str) -> str:
        try:
            return subprocess.run(
                ["git", *cmd],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return ""

    dirty = bool(run("status", "--porcelain"))
    return {
        "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
        "commit": run("rev-parse", "--short", "HEAD") + ("-dirty" if dirty else ""),
    }


def write_summary(recs: list[dict], jsonl_path: Path) -> dict:
    summary = summarize(recs)
    summary["methods"] = sorted({r.get("method") or DEFAULT_METHOD for r in recs})
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


def run_graph(
    rows: list[dict],
    out_path: Path,
    method: str,
    params: dict[str, str],
) -> list[dict]:
    from dotenv import load_dotenv
    from langfuse import get_client
    from langfuse.langchain import CallbackHandler

    from graph.graph import app

    load_dotenv()
    lf = get_client()
    git = git_info()
    run_meta = {"method": method, "params": params, **git}
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
                        "langfuse_tags": ["gold", method, tag],
                        "gold_id": row["id"],
                        "ncm_gold": row["ncm_gold"],
                        **run_meta,
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
                    metadata={"gold_id": row["id"], "tag": tag, **run_meta},
                )
            lf.create_score(
                name="wall_s",
                value=wall,
                trace_id=trace_id,
                data_type="NUMERIC",
                metadata={"gold_id": row["id"], "tag": tag, **run_meta},
            )
            lf.flush()
            rec = {
                "id": row["id"],
                "tag": row.get("tag"),
                "method": method,
                "params": params,
                "commit": git["commit"],
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
    out = args.out or RESULTS_DIR / f"{args.method}.jsonl"
    run_graph(rows, out, args.method, parse_params(args.param))
    write_summary(load_jsonl(out), out)


if __name__ == "__main__":
    main()
