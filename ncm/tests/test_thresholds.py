from ncm.thresholds import (
    extract_constraints,
    extract_specs,
    filter_items,
    item_conflicts,
)


def test_boiler_20_tph_conflicts_with_over_45():
    question = "Caldera acuotubular de vapor 20 toneladas por hora CIF 80000 USD origen China"
    over = "Calderas acuotubulares con una producción de vapor superior a 45 t por hora"
    under = "Calderas acuotubulares con una producción de vapor inferior o igual a 45 t por hora"
    assert extract_specs(question) == [(20.0, "t/h")]
    assert extract_constraints(over) == [(">", 45.0, "t/h")]
    assert extract_constraints(under) == [("<=", 45.0, "t/h")]
    assert item_conflicts(question, over) is True
    assert item_conflicts(question, under) is False
    assert item_conflicts("coffee CIF 4.50", over) is False


def test_cif_amount_is_not_a_capacity():
    specs = extract_specs("caldera CIF 80000 USD")
    assert (80000.0, "t/h") not in specs
    assert (80000.0, "t") not in specs


def test_filter_items_keeps_matching_boiler():
    items = [
        {
            "ncm": "8402.11.00",
            "full_description": "superior a 45 t por hora",
        },
        {
            "ncm": "8402.12.00",
            "full_description": "inferior o igual a 45 t por hora",
        },
        {
            "ncm": "8402.19.00",
            "full_description": "Las demás calderas de vapor, incluidas las calderas mixtas",
        },
    ]
    kept = filter_items("caldera 20 toneladas por hora CIF 80000", items)
    assert [i["ncm"] for i in kept] == ["8402.12.00"]
    kept_big = filter_items("caldera 50 toneladas por hora CIF 80000", items)
    assert [i["ncm"] for i in kept_big] == ["8402.11.00"]


def test_filter_items_untouched_without_comparable_number():
    items = [
        {"ncm": "0901.11.10", "full_description": "Café en grano"},
        {"ncm": "0901.11.90", "full_description": "Los demás"},
    ]
    kept = filter_items("green coffee beans CIF 4.50", items)
    assert [i["ncm"] for i in kept] == ["0901.11.10", "0901.11.90"]
