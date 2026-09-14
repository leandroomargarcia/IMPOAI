from ncm.parser import (
    CATALOG_PATH,
    CATALOG_POC_PATH,
    PDF_PATH,
    POC_CHAPTERS,
    extract_pdf_text,
    parse_ncm,
    save_catalog,
    _strip_aero,
)

if __name__ == "__main__":
    raw = _strip_aero(extract_pdf_text(PDF_PATH))
    data = parse_ncm(text=raw)
    out = save_catalog(data, CATALOG_PATH)
    save_catalog(parse_ncm(text=raw, chapters=POC_CHAPTERS), CATALOG_POC_PATH)
    print(
        f"capitulos={len(data['chapters'])} "
        f"nodos={len(data['nodes'])} "
        f"items={len(data['items'])} -> {out}"
    )
