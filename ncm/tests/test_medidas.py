import pytest

from ncm.medidas import (
    extract_ad_valorem,
    extract_especifico,
    latest_medidas_xlsx,
    load_medidas,
    origin_matches,
    parse_ncm_list,
    rate_for_origin,
    specific_for_origin,
)


def test_parse_ncm_list_split_y_and_comma():
    codes = parse_ncm_list("8211.10.00, 8211.91.00, 8215.20.00 Y 8215.99.10")
    assert codes == ["8211.10.00", "8211.91.00", "8215.20.00", "8215.99.10"]


def test_extract_ad_valorem_by_country():
    rates = extract_ad_valorem(
        "Derecho ad valorem. Alemania: 138%. China: 208%.",
        "Alemania, China",
    )
    assert rates["alemania"] == 138.0
    assert rates["china"] == 208.0


def test_extract_single_percent_applies_to_origin():
    rates = extract_ad_valorem(
        "Derecho antidumping ad valorem de 246%.",
        "China",
    )
    assert rates["china"] == 246.0


def test_rate_for_origin_picks_matching_country():
    medida = "Derecho ad valorem. Brasil: 24%. China: 202,79%."
    assert rate_for_origin(medida, "Brasil, China", "China") == pytest.approx(202.79)
    assert rate_for_origin(medida, "Brasil, China", "Brasil") == pytest.approx(24)
    assert rate_for_origin(medida, "Brasil, China", "India") is None


def test_origin_matches_ignores_accents():
    assert origin_matches("China", "Brasil, China, India")
    assert origin_matches("vietnam", "Malasia, Vietnám")
    assert not origin_matches("Chile", "Brasil, China")


def test_specific_picks_country_rate():
    medida = (
        "Derechos específicos: China: U$S 0,46 por unidad, "
        "Tailandia: U$S 0,21 por unidad."
    )
    assert extract_especifico(medida)[0]["usd"] == pytest.approx(0.46)
    picked = specific_for_origin(medida, "China, Tailandia", "China")
    assert picked == {"usd": 0.46, "unit": "unidad"}
    assert specific_for_origin(
        "US$ 13,22 por unidad a las secas, y de US$ 15,41 por unidad a vapor.",
        "China",
        "China",
    ) is None


@pytest.mark.skipif(latest_medidas_xlsx() is None, reason="no medidas xlsx in docs/")
def test_live_xlsx_known_ncm():
    index = load_medidas()
    assert index.for_ncm("8413.30.90")
    assert index.for_ncm("8413.30.90")[0]["ad_valorem"]["china"] == 246.0
    assert not index.for_ncm("0901.11.10")
    tires = index.for_ncm("4011.50.00")
    assert tires
    assert tires[0]["kind"] == "min_fob"
