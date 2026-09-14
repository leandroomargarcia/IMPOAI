import json


def tavily_hits(raw, *, keep_raw_text: bool = False) -> list:
    """Normalize Tavily output (dict, JSON string, or plain text)."""
    leftover = ""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            leftover = raw.strip()
            raw = {}
    if not isinstance(raw, dict):
        return []

    hits = [h for h in (raw.get("results") or []) if isinstance(h, dict)]
    answer = raw.get("answer")
    if isinstance(answer, str) and answer.strip():
        hits.insert(0, {"title": "tavily_answer", "content": answer, "url": ""})
    if keep_raw_text and leftover and not hits:
        hits.append({"title": "tavily", "content": leftover, "url": ""})
    return hits
