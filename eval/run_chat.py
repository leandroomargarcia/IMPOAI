"""Live chat-gold job. Not part of default pytest (calls the chat LLM).

Default: mock the office so we score routing / CIF, not hit8.
`--live` runs only `live: true` integrate rows against the real graph.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.chat_metrics import langfuse_scores, parse_sse, score_turn, summarize_chat

GOLD_PATH = ROOT / "eval" / "chat_gold.json"
RESULTS_DIR = ROOT / "eval" / "results"
DATASET_NAME = "chat-v1"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=1)
    p.add_argument("--id", dest="row_id", default="")
    p.add_argument("--gold", type=Path, default=GOLD_PATH)
    p.add_argument("--out", type=Path, default=RESULTS_DIR / "chat.jsonl")
    p.add_argument(
        "--from-jsonl",
        type=Path,
        default=None,
        help="Score an existing jsonl; do not call the chat.",
    )
    p.add_argument(
        "--live",
        action="store_true",
        help="Run integrate rows against the real office (OpenAI + Tavily).",
    )
    p.add_argument(
        "--run-name",
        default="",
        help="Langfuse dataset run name. Default: chat-v1-<utc>.",
    )
    return p.parse_args()


def write_summary(recs: list[dict], jsonl_path: Path) -> dict:
    summary = summarize_chat(recs)
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


def _select(rows: list[dict], args: argparse.Namespace) -> list[dict]:
    if args.row_id:
        rows = [r for r in rows if r["id"] == args.row_id]
        if not rows:
            raise SystemExit(f"unknown id: {args.row_id}")
    elif args.live:
        rows = [r for r in rows if r.get("live")]
        if not rows:
            raise SystemExit("no live integrate rows")
    else:
        rows = [r for r in rows if not r.get("live")]
    return rows[: args.limit]


def _mock_office(question: str, tags=None) -> dict:
    return {
        "ncm": "9999.99.99",
        "ncm_descripcion": "mock / eval",
        "cif": 1.0,
        "impuestos_estimados": 1.0,
        "costos_asociados": "CIF mock",
        "es_valido": True,
    }


async def _one_turn(session_id: str, message: str) -> str:
    from api.chat import ChatIn, _events

    chunks = []
    async for part in _events(ChatIn(session_id=session_id, message=message)):
        chunks.append(part)
    return "".join(chunks)


def _ensure_dataset(lf, rows: list[dict]) -> str | None:
    try:
        ds = lf.get_dataset(DATASET_NAME)
        return getattr(ds, "id", None) or DATASET_NAME
    except Exception:
        pass
    try:
        created = lf.create_dataset(
            name=DATASET_NAME,
            description=(
                "Chat v1 gold: FAQ / CIF gate / sequential products / "
                "jailbreak / office integrate."
            ),
            metadata={"layer": "chat", "v": 1},
        )
        return getattr(created, "id", None) or DATASET_NAME
    except Exception as exc:
        print("langfuse dataset skip:", exc, flush=True)
        return None


def _upsert_items(lf, rows: list[dict]) -> None:
    for row in rows:
        try:
            lf.create_dataset_item(
                dataset_name=DATASET_NAME,
                id=row["id"],
                input={"id": row["id"], "tag": row.get("tag"), "turns": row["turns"]},
                expected_output={
                    "turns": [t.get("expect") for t in row["turns"]],
                    "live": bool(row.get("live")),
                },
                metadata={"tag": row.get("tag"), "live": bool(row.get("live"))},
            )
        except Exception as exc:
            print("langfuse item skip", row["id"], exc, flush=True)


def run_chat(rows: list[dict], out_path: Path, *, live: bool, run_name: str) -> list[dict]:
    from dotenv import load_dotenv
    from langfuse import get_client
    from langfuse.langchain import CallbackHandler

    import api.office as office
    import api.office_tool as office_tool
    from api.chat import CHAT_CALLBACKS, SESSIONS

    load_dotenv()
    lf = get_client()
    _ensure_dataset(lf, rows)
    _upsert_items(lf, rows)

    real_office = office.invoke_office
    real_tool_office = office_tool.invoke_office
    if not live:
        office.invoke_office = _mock_office
        office_tool.invoke_office = _mock_office

    out_path.parent.mkdir(parents=True, exist_ok=True)
    recs: list[dict] = []
    try:
        with out_path.open("a", encoding="utf-8") as fh:
            for row in rows:
                tag = row.get("tag") or "untagged"
                session_id = f"gold-{row['id']}"
                SESSIONS.pop(session_id, None)
                users = [t["user"] for t in row["turns"]]
                trace_id = lf.create_trace_id()
                handler = CallbackHandler(trace_context={"trace_id": trace_id})
                token = CHAT_CALLBACKS.set([handler])
                dialogue_out = []
                try:
                    with lf.start_as_current_observation(
                        name=row["id"],
                        as_type="span",
                        trace_context={"trace_id": trace_id},
                        input={"id": row["id"], "tag": tag, "turns": users},
                        metadata={
                            "langfuse_tags": ["chat", "gold", tag],
                            "gold_id": row["id"],
                            "run_name": run_name,
                        },
                    ) as span:
                        for i, turn in enumerate(row["turns"]):
                            t0 = time.perf_counter()
                            body = asyncio.run(_one_turn(session_id, turn["user"]))
                            wall = round(time.perf_counter() - t0, 3)
                            parsed = parse_sse(body)
                            scored = score_turn(
                                turn.get("expect") or {},
                                tokens=parsed["tokens"],
                                card=parsed["card"],
                            )
                            rec = {
                                "id": row["id"],
                                "tag": tag,
                                "turn": i,
                                "live": bool(live and row.get("live")),
                                "user": turn["user"],
                                "tokens": parsed["tokens"],
                                "error": parsed["error"],
                                "wall_s": wall,
                                "trace_id": trace_id,
                                **scored,
                            }
                            comment = (
                                f"id={row['id']} turn={i} "
                                f"tool={rec.get('used_tool')} want={rec.get('want_tool')}"
                            )
                            for name, value, data_type in langfuse_scores(rec):
                                span.score_trace(
                                    name=name,
                                    value=value,
                                    data_type=data_type,
                                    comment=comment,
                                    metadata={
                                        "gold_id": row["id"],
                                        "tag": tag,
                                        "turn": i,
                                    },
                                )
                            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                            fh.flush()
                            recs.append(rec)
                            dialogue_out.append(
                                {
                                    "turn": i,
                                    "tool": rec.get("used_tool"),
                                    "ok": rec.get("chat_turn_ok"),
                                }
                            )
                            print(
                                rec["id"],
                                "turn",
                                i,
                                "tool",
                                rec.get("used_tool"),
                                "ok",
                                rec.get("chat_turn_ok"),
                                "wall",
                                wall,
                                flush=True,
                            )
                        span.update(output=dialogue_out)
                    try:
                        lf.create_dataset_item(
                            dataset_name=DATASET_NAME,
                            id=row["id"],
                            input={
                                "id": row["id"],
                                "tag": tag,
                                "turns": row["turns"],
                            },
                            expected_output={
                                "turns": [t.get("expect") for t in row["turns"]],
                            },
                            metadata={"tag": tag, "live": bool(row.get("live"))},
                            source_trace_id=trace_id,
                        )
                    except Exception as exc:
                        print("langfuse item skip", row["id"], exc, flush=True)
                finally:
                    CHAT_CALLBACKS.reset(token)
                lf.flush()
    finally:
        office.invoke_office = real_office
        office_tool.invoke_office = real_tool_office
    return recs


def main() -> None:
    args = parse_args()
    if args.from_jsonl:
        recs = load_jsonl(args.from_jsonl)
        write_summary(recs, args.from_jsonl)
        return

    from datetime import datetime, timezone

    rows = json.loads(args.gold.read_text(encoding="utf-8"))
    rows = _select(rows, args)
    run_name = args.run_name or (
        "chat-v1-live-" if args.live else "chat-v1-"
    ) + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_chat(rows, args.out, live=args.live, run_name=run_name)
    write_summary(load_jsonl(args.out), args.out)


if __name__ == "__main__":
    main()
