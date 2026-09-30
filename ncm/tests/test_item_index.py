from ncm.item_index import ItemIndex, stem, tokens

ITEMS = [
    {"codigo": "0901.11.10", "partida": "09.01",
     "descripcion_completa": "Café, incluso tostado o descafeinado / Sin descafeinar / En grano"},
    {"codigo": "9403.50.00", "partida": "94.03",
     "descripcion_completa": "Los demás muebles y sus partes. / Muebles de madera de los tipos utilizados en los dormitorios"},
    {"codigo": "4420.90.00", "partida": "44.20",
     "descripcion_completa": "Marquetería y taracea; cofrecillos y estuches para joyería, de madera / Los demás"},
]


def test_tokens_fold_and_stem():
    assert tokens("Muebles de Dormitorio") == ["muebl", "dormitori"]
    assert stem("azúcares".replace("ú", "u")) == stem("azucar")


def test_search_finds_item_outside_wood_chapter():
    hits = ItemIndex(ITEMS).search("juego de dormitorio de madera")
    assert hits[0]["ncm"] == "9403.50.00"
    assert hits[0]["partida"] == "94.03"


def test_search_ignores_unknown_terms():
    assert ItemIndex(ITEMS).search("zzz qqq") == []