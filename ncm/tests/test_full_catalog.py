import pytest

from ncm.parser import CATALOG_PATH


@pytest.fixture(scope="session")
def full_catalog():
    if not CATALOG_PATH.exists():
        pytest.skip("ncm/data/catalog.json missing; run python -m ncm")
    import json

    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def test_full_catalog_has_97_chapters(full_catalog):
    codes = [c["codigo"] for c in full_catalog["chapters"]]
    assert codes == [f"{n:02d}" for n in range(1, 98)]
    assert "SECTOR AERONÁUTICO" not in full_catalog["rgi"]
    assert full_catalog["items"]
    assert all(i["nivel"] == 8 and i["aec"] is not None for i in full_catalog["items"])


def test_full_catalog_poc_regression(full_catalog):
    by_code = {n["codigo"]: n for n in full_catalog["items"]}
    assert by_code["0901.11.10"]["aec"] == 10
    assert by_code["0101.21.00"]["aec"] == 0
    yerba = by_code["0903.00.10"]
    assert "canchada" in yerba["descripcion"].lower()
    path = yerba["descripcion_completa"].lower()
    assert "yerba" in path
    assert "té" not in path and "te," not in path


def test_short_chapter_title_strips_leaked_notes(full_catalog):
    from ncm.catalog import short_chapter_title

    by_code = {c["codigo"]: c["titulo"] for c in full_catalog["chapters"]}
    assert len(by_code["52"]) > 1000
    assert short_chapter_title(by_code["52"]).lower() == "algodón"
    assert "52.01" not in short_chapter_title(by_code["53"])


def test_full_catalog_spot_check_27_39_84(full_catalog):
    titles = {c["codigo"]: c["titulo"].lower() for c in full_catalog["chapters"]}
    assert "combustible" in titles["27"]
    assert "plástico" in titles["39"] or "plastico" in titles["39"]
    assert "máquina" in titles["84"] or "maquina" in titles["84"] or "caldera" in titles["84"]

    by_code = {n["codigo"]: n for n in full_catalog["nodes"]}
    nafta = by_code["2710.12.41"]
    assert nafta["aec"] == 0
    assert nafta["capitulo"] == "27"

    pe = by_code["3901.10.10"]
    assert pe["aec"] == 14
    assert pe["capitulo"] == "39"
    assert "lineal" in pe["descripcion"].lower()

    reactor = by_code["8401.10.00"]
    assert reactor["aec"] == 14
    assert reactor["aec_flag"] == "BK"
    assert reactor["capitulo"] == "84"

