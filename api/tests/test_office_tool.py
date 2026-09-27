from api.guardrails import Slots
from api.office_tool import merge_slots, run_classify


def test_merge_ignores_tool_invented_cif():
    slots = Slots(product="aspiradoras", cif=None, origen="China")
    merged = merge_slots({"product": "aspiradoras", "cif_usd": 1000}, slots)
    assert merged.cif is None
    assert merged.product == "aspiradoras"


def test_run_classify_needs_user_cif(monkeypatch):
    monkeypatch.setattr(
        "api.office_tool.invoke_office",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("office")),
    )
    out = run_classify(
        {"product": "aspiradoras", "cif_usd": 1000},
        Slots(product="aspiradoras", cif=None),
    )
    assert out.get("error")
    assert "CIF" in out["error"]
