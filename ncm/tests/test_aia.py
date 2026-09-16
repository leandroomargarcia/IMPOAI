import pytest

from ncm.aia import latest_docs_file, load_aia, parse_capitulo, parse_nomenclador
from ncm.catalog import NcmCatalog


SAMPLE_NOMENCLADOR = """
2@0901.11.10      @      @      @      @      @      @      @  @  @   En grano
2@0901.11.10.100U @000.00@001.00@009.00@001.00@000.00@      @01@  @      Arabigos
2@0101.21.00.100W @006.50@000.50@000.00@000.50@000.00@      @01@  @      Sangre pura de carrera
2@3004.90.19.900E @000.00@007.00@007.20@007.00@000.00@      @01@  @      Los demas
"""

SAMPLE_CAPITULO = """
1@00@ nota al lector
1@01@ CAPITULO 1 ANIMALES VIVOS Nota. 1. Este Capitulo no comprende los peces.
"""


def test_parse_nomenclador_die():
    by_ncm = parse_nomenclador(SAMPLE_NOMENCLADOR)
    assert by_ncm["0901.11.10"]["die"] == 9.0
    assert by_ncm["0901.11.10"]["description"] == "En grano"
    assert by_ncm["0101.21.00"]["die"] == 0.0
    assert by_ncm["3004.90.19"]["die"] == 7.2


def test_parse_capitulo_skips_00():
    notes = parse_capitulo(SAMPLE_CAPITULO)
    assert "01" in notes
    assert "peces" in notes["01"].lower()
    assert "00" not in notes


def test_catalog_overlays_aia_die(catalog_data, tmp_path):
    (tmp_path / "nomenclador_15092026.txt").write_text(SAMPLE_NOMENCLADOR, encoding="latin-1")
    (tmp_path / "capitulo_15092026.txt").write_text(SAMPLE_CAPITULO, encoding="latin-1")
    aia = load_aia(tmp_path)
    cat = NcmCatalog(catalog_data, aia=aia)
    cafe = cat.get_ncm("0901.11.10")
    assert cafe["aec"] == 9.0
    caballo = cat.get_ncm("0101.21.00")
    assert caballo["aec"] == 0.0
    assert "peces" in cat.get_notes("01")["chapter_notes"].lower()


def test_catalog_without_aia_keeps_pdf_aec(catalog_data):
    cat = NcmCatalog(catalog_data)
    assert cat.get_ncm("0901.11.10")["aec"] == 10


@pytest.mark.skipif(latest_docs_file("nomenclador") is None, reason="no AIA dump in docs/")
def test_live_dump_known_dies():
    aia = load_aia()
    assert aia.die("0901.11.10") == 9.0
    assert aia.die("0101.21.00") == 0.0
    assert aia.die("3004.90.19") == 7.2
    assert "01" in aia.chapter_notes
