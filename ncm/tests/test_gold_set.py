import json
from collections import Counter
from pathlib import Path

from ncm.parser import CATALOG_PATH

GOLD = Path(__file__).resolve().parents[2] / "eval" / "gold.json"


def test_gold_has_50_catalog_ncms():
    if not CATALOG_PATH.exists():
        import pytest

        pytest.skip("ncm/data/catalog.json missing")
    rows = json.loads(GOLD.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    assert len(rows) == 50
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids))
    items = {n["codigo"] for n in catalog["items"]}
    for row in rows:
        assert row["ncm_gold"] in items, row["id"]
        assert "CIF" in row["question"]
        assert row["tag"]
    cons = [r["id"] for r in rows if r.get("consistency")]
    assert len(cons) == 10
    tags = Counter(r["tag"] for r in rows)
    assert tags["typical"] == 35
    assert sum(v for t, v in tags.items() if t != "typical") == 15
