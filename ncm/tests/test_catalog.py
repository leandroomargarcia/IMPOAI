from ncm.catalog import NcmCatalog


def test_tools_lookup(catalog_data):
    cat = NcmCatalog(catalog_data)
    caps = cat.buscar_capitulos("café en grano")
    assert caps[0]["capitulo"] == "09"

    notas = cat.get_notas("09")
    assert "yerba" in notas["titulo"].lower()

    partidas = cat.listar_partidas("09")
    assert any(p["partida"] == "09.01" for p in partidas)
    assert any(p["partida"] == "09.03" for p in partidas)

    items = cat.listar_items("09.01")
    assert any(i["ncm"] == "0901.11.10" for i in items)

    ficha = cat.get_ncm("0901.11.10")
    assert ficha["aec"] == 10
    assert cat.get_ncm("9999.99.99") is None
