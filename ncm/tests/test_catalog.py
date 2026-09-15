from ncm.catalog import NcmCatalog


def test_tools_lookup(catalog_data):
    cat = NcmCatalog(catalog_data)
    caps = cat.search_chapters("café en grano")
    assert caps[0]["chapter"] == "09"

    notas = cat.get_notes("09")
    assert "yerba" in notas["title"].lower()

    partidas = cat.list_headings("09")
    assert any(p["heading"] == "09.01" for p in partidas)
    assert any(p["heading"] == "09.03" for p in partidas)

    items = cat.list_items("09.01")
    assert any(i["ncm"] == "0901.11.10" for i in items)

    grano = cat.list_items("0901.11")
    assert {i["ncm"] for i in grano} == {"0901.11.10", "0901.11.90"}
    assert any(s["subheading"] == "0901.11" for s in cat.list_subheadings("09.01"))

    ficha = cat.get_ncm("0901.11.10")
    assert ficha["aec"] == 10
    assert cat.get_ncm("9999.99.99") is None
