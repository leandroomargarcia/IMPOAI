def _item(data, codigo):
    matches = [i for i in data["items"] if i["codigo"] == codigo]
    assert matches, f"falta {codigo}"
    return matches[0]


def test_poc_parsea_capitulos_1_y_9(catalog_data):
    assert {c["codigo"] for c in catalog_data["chapters"]} == {"01", "09"}
    assert "REGLAS GENERALES" in catalog_data["rgi"]
    assert "SECTOR AERONÁUTICO" not in catalog_data["rgi"]
    assert catalog_data["items"]


def test_cafe_en_grano_reconstruye_jerarquia(catalog_data):
    cafe = _item(catalog_data, "0901.11.10")
    assert cafe["aec"] == 10
    assert cafe["re"] == "3,50"
    path = cafe["descripcion_completa"].lower()
    assert "café" in path
    assert "sin tostar" in path
    assert "sin descafeinar" in path
    assert "grano" in path


def test_caballo_reproductor(catalog_data):
    caballo = _item(catalog_data, "0101.21.00")
    assert caballo["aec"] == 0
    path = caballo["descripcion_completa"].lower()
    assert "caballos" in path
    assert "raza pura" in path


def test_yerba_mate_canchada(catalog_data):
    yerba = _item(catalog_data, "0903.00.10")
    assert yerba["partida"] == "09.03"
    assert "canchada" in yerba["descripcion"].lower()
    path = yerba["descripcion_completa"].lower()
    assert "yerba" in path
    assert "té" not in path and "te," not in path


def test_notas_capitulo_1_excluyen_peces(catalog_data):
    ch1 = next(c for c in catalog_data["chapters"] if c["codigo"] == "01")
    assert "peces" in ch1["notas"].lower()
