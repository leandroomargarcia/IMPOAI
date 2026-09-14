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

    ficha = cat.get_ncm("0901.11.10")
    assert ficha["aec"] == 10
    assert cat.get_ncm("9999.99.99") is None
