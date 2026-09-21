from eval.metrics import hits, percentile, summarize


def test_hits_hierarchy():
    h = hits("0402.29.20", "0402.10.10")
    assert h["hit2"] is True
    assert h["hit4"] is True
    assert h["hit6"] is False
    assert h["hit8"] is False
    assert hits("1509.10.00", "1509.10.00")["hit8"] is True


def test_summarize_v1_smoke_jsonl():
    recs = [
        {
            "id": "a",
            "tag": "typical",
            "ncm_pred": "1509.10.00",
            "hit2": True,
            "hit4": True,
            "hit6": True,
            "hit8": True,
            "wall_s": 5.0,
            "grade": True,
            "attempts": 1,
        },
        {
            "id": "b",
            "tag": "typical",
            "ncm_pred": "0402.29.20",
            "hit2": True,
            "hit4": True,
            "hit6": False,
            "hit8": False,
            "wall_s": 9.0,
            "grade": True,
            "attempts": 1,
        },
    ]
    s = summarize(recs)
    assert s["n"] == 2
    assert s["accuracy"]["hit8"] == 50.0
    assert s["accuracy"]["hit4"] == 100.0
    assert s["recall8"] == s["precision8"] == 50.0
    assert s["by_tag"]["typical"]["hit8"] == 50.0
    assert percentile([5.0, 9.0], 50) == 5.0
    assert s["latency_s"]["p50"] == 5.0
    assert s["fail_grade"] == 0
    assert s["retries"] == 0
