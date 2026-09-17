import re

from graph.consts import (
    ESTADISTICA_CAPS,
    ESTADISTICA_RATE,
    GANANCIAS_PERC_CVDI,
    GANANCIAS_PERC_INSCRIPTO,
    GANANCIAS_PERC_PARTICULAR,
    IIBB_ALIASES,
    IIBB_RATES,
    IVA_PERC_GENERAL,
    IVA_PERC_REDUCED,
    IVA_RATE,
    IVA_REDUCED_FLAGS,
    IVA_REDUCED_RATE,
    MERCOSUR_ORIGINS,
)
from graph.state import GraphState
from ncm.medidas import (
    fold,
    norm_unit,
    origin_matches,
    rate_for_origin,
    specific_for_origin,
)

_NUM = r"(\d+(?:[.,]\d+)?)"
CIF_RE = re.compile(rf"\bcif\s*[:=]?\s*{_NUM}", re.I)
ORIGEN_RE = re.compile(
    r"\b(?:origen|origin|procedencia)\s*[:=]?\s*([A-Za-zÁÉÍÓÚáéíóúñüÑ]+(?:\s+[A-Za-zÁÉÍÓÚáéíóúñüÑ]+)?)",
    re.I,
)
CANT_RE = re.compile(
    rf"(?<![.\d]){_NUM}\s*"
    r"(?P<unit>unidad(?:es)?|kilogramos?|kg|metros?(?:\s+lineales?|\s+cuadrados?)?|m2|pares?)\b",
    re.I,
)
VALUE_CLAUSE_RE = re.compile(
    rf"\b(?:cif|fob|flete|freight|seguro|insurance)\s*[:=]?\s*{_NUM}(?:\s*usd)?"
    r"|\b(?:origen|origin|procedencia)\s*[:=]?\s*[A-Za-zÁÉÍÓÚáéíóúñüÑ]+(?:\s+[A-Za-zÁÉÍÓÚáéíóúñüÑ]+)?"
    rf"|{_NUM}\s*(?:unidad(?:es)?|kilogramos?|kg|metros?(?:\s+lineales?|\s+cuadrados?)?|m2|pares?)\b"
    r"|\b(?:responsable\s+)?(?:no\s+)?inscripto\b"
    r"|\bmonotributista\b"
    r"|\b(?:uso|consumo)\s+particular\b"
    r"|\bconsumidor\s+final\b"
    r"|\bcvdi\b"
    r"|\biva\s*[:=]?\s*\d+(?:[.,]\d+)?\s*%?"
    r"|\bexento\s+(?:de\s+)?iva\b"
    r"|\bcertificado\s+de\s+exclusi[oó]n\b"
    r"|\b(?:provincia|jurisdicci[oó]n)(?:\s+de)?\s*[:=]?\s*[A-Za-zÁÉÍÓÚáéíóúñüÑ]+(?:\s+(?:de|del|los|las|el)?\s*[A-Za-zÁÉÍÓÚáéíóúñüÑ]+){0,4}"
    r"|\biibb\s*[:=]?\s*\d+(?:[.,]\d+)?\s*%?",
    re.I,
)
INSCRIPTO_NO_RE = re.compile(
    r"\bno\s*inscripto\b|\bmonotribut|\bconsumidor\s+final\b"
    r"|\b(?:uso|consumo)\s+particular\b",
    re.I,
)
INSCRIPTO_YES_RE = re.compile(
    r"(?:responsable|resp\.?)\s+inscripto|\binscripto\b",
    re.I,
)
IVA_RATE_RE = re.compile(rf"\biva\s*[:=]?\s*{_NUM}\s*%?", re.I)
IVA_EXENTO_RE = re.compile(r"\bexento\s+(?:de\s+)?iva\b|\biva\s+exento\b", re.I)
IVA_REDUCED_RE = re.compile(r"\biva\s+reducido\b|\bal[ií]cuota\s+reducida\b", re.I)
CVDI_RE = re.compile(r"\bcvdi\b|certificado\s+de\s+validaci[oó]n", re.I)
EXCLUSION_RE = re.compile(
    r"exclusi[oó]n\s+(?:de\s+)?ganancias|certificado\s+de\s+exclusi[oó]n"
    r"|no\s+retenci[oó]n\s+ganancias",
    re.I,
)
PROVINCIA_RE = re.compile(
    r"\b(?:provincia|jurisdicci[oó]n)(?:\s+de)?\s*[:=]?\s*",
    re.I,
)
IIBB_RATE_RE = re.compile(rf"\biibb\s*[:=]?\s*{_NUM}\s*%?", re.I)


def parse_cif(question: str) -> float | None:
    match = CIF_RE.search(question or "")
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def parse_origen(question: str) -> str | None:
    match = ORIGEN_RE.search(question or "")
    if not match:
        return None
    return match.group(1).strip()


def parse_cantidad(question: str) -> tuple[float, str] | None:
    match = CANT_RE.search(question or "")
    if not match:
        return None
    unit = norm_unit(match.group("unit"))
    if not unit:
        return None
    return float(match.group(1).replace(",", ".")), unit


def parse_inscripto(question: str) -> bool:
    """Default False: monotributista. True only if the question says inscripto."""
    text = question or ""
    if INSCRIPTO_NO_RE.search(text):
        return False
    return bool(INSCRIPTO_YES_RE.search(text))


def parse_iva_rate(question: str, aec_flag: str | None = None) -> float:
    return iva_rate_for(question, aec_flag)[0]


def iva_rate_for(question: str, aec_flag: str | None = None) -> tuple[float, str]:
    """Question override wins. Else BK/BIT → 10.5 %. Else 21 %."""
    text = question or ""
    if IVA_EXENTO_RE.search(text):
        return 0.0, "pregunta"
    match = IVA_RATE_RE.search(text)
    if match:
        return float(match.group(1).replace(",", ".")), "pregunta"
    if IVA_REDUCED_RE.search(text):
        return IVA_REDUCED_RATE, "pregunta"
    flag = (aec_flag or "").strip().upper()
    if flag in IVA_REDUCED_FLAGS:
        return IVA_REDUCED_RATE, f"NCM {flag}"
    return IVA_RATE, "default"


def parse_provincia(question: str) -> str | None:
    """Canonical province, '' if mentioned but unknown, None if omitted."""
    match = PROVINCIA_RE.search(question or "")
    if not match:
        return None
    rest = fold(question[match.end() :]).replace(".", "").replace(" ", "")
    if not rest:
        return ""
    for key in sorted(IIBB_ALIASES, key=len, reverse=True):
        if rest.startswith(key):
            return IIBB_ALIASES[key]
    return ""


def parse_iibb_rate(question: str) -> float | None:
    match = IIBB_RATE_RE.search(question or "")
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def strip_cif_clause(question: str) -> str:
    text = VALUE_CLAUSE_RE.sub("", question or "")
    return re.sub(r"\s+", " ", text).strip(" ,;-")


strip_fob_clause = strip_cif_clause


def is_mercosur_origin(origen: str | None) -> bool:
    key = fold(origen or "").replace(" ", "")
    if not key:
        return False
    return any(key == m or key in m or m in key for m in MERCOSUR_ORIGINS)


def estadistica_cap(cif: float) -> float:
    for limit, cap in ESTADISTICA_CAPS:
        if cif <= limit:
            return cap
    return ESTADISTICA_CAPS[-1][1]


def calc_estadistica(cif: float, origen: str | None) -> tuple[float, str]:
    """3 % of CIF, capped (Decree 1140/2024). Mercosur origin is exempt."""
    if is_mercosur_origin(origen):
        return 0.0, f"Tasa de estadística 0 USD (origen Mercosur: {origen})"
    raw = cif * (ESTADISTICA_RATE / 100)
    cap = estadistica_cap(cif)
    amount = min(raw, cap)
    note = (
        f"Tasa de estadística {ESTADISTICA_RATE:g}% sobre CIF = {amount:g} USD"
        + (f" (tope {cap:g})" if amount < raw else "")
    )
    if not origen:
        note += " (extra-zona; si el origen es Mercosur, esta tasa es 0)"
    return amount, note


def iva_base(cif: float, die: float, te: float, extra: float) -> float:
    return cif + die + te + extra


def perc_iva_rate(iva_rate: float) -> float:
    if iva_rate <= 0:
        return 0.0
    if iva_rate <= IVA_REDUCED_RATE:
        return IVA_PERC_REDUCED
    return IVA_PERC_GENERAL


def ganancias_rate(question: str, inscripto: bool) -> tuple[float, str]:
    """RG 2281: 11% monotributista (default), 6% inscripto, 3% C.V.D.I."""
    text = question or ""
    if EXCLUSION_RE.search(text):
        return 0.0, "exclusión RG 830"
    if re.search(r"consumo\s+particular|uso\s+particular|consumidor\s+final", text, re.I):
        return (
            GANANCIAS_PERC_PARTICULAR,
            "uso o consumo particular",
        )
    if not inscripto:
        return GANANCIAS_PERC_PARTICULAR, "monotributista"
    if CVDI_RE.search(text):
        return GANANCIAS_PERC_CVDI, "C.V.D.I."
    return GANANCIAS_PERC_INSCRIPTO, "inscripto sin C.V.D.I."


def calc_iva(
    cif: float,
    die: float,
    te: float,
    extra: float,
    rate: float | None = None,
    source: str | None = None,
) -> tuple[float, str]:
    """IVA on CIF + DIE + estadística + dumping extras (Ley IVA art. 25)."""
    rate = IVA_RATE if rate is None else rate
    if source is None:
        source = "default" if rate == IVA_RATE else "pregunta"
    base = iva_base(cif, die, te, extra)
    amount = base * (rate / 100)
    if source.startswith("NCM "):
        hint = "asume uso productivo; no es tabla 10,5% de alimentos"
    elif source == "pregunta":
        hint = "override en la pregunta"
    else:
        hint = "no es tabla 10,5% por NCM de alimentos"
    note = (
        f"IVA {rate:g}% sobre CIF+DIE+estadística+medidas ({base:g} USD) "
        f"= {amount:g} USD ({source}; {hint})"
    )
    return amount, note


def calc_iva_percepcion(
    cif: float, die: float, te: float, extra: float, iva_rate: float
) -> tuple[float, str]:
    """RG 2937/4461: 20% if IVA 21%, 10% if IVA 10.5%, same art. 25 base."""
    base = iva_base(cif, die, te, extra)
    rate = perc_iva_rate(iva_rate)
    amount = base * (rate / 100)
    note = (
        f"Percepción IVA {rate:g}% (RG 2937) sobre la misma base ({base:g} USD) "
        f"= {amount:g} USD"
    )
    if iva_rate <= 0:
        note = "Percepción IVA 0 USD (IVA exento)"
    return amount, note


def calc_ganancias(
    cif: float, die: float, te: float, extra: float, question: str, inscripto: bool
) -> tuple[float, str]:
    """RG 2281 on CIF + DIE + estadística + medidas (IVA deducted, art. 6)."""
    rate, kind = ganancias_rate(question, inscripto)
    base = iva_base(cif, die, te, extra)
    amount = base * (rate / 100)
    note = (
        f"Percepción Ganancias {rate:g}% (RG 2281, {kind}) sobre "
        f"CIF+DIE+estadística+medidas ({base:g} USD) = {amount:g} USD"
    )
    return amount, note


def calc_iibb(
    cif: float,
    die: float,
    te: float,
    extra: float,
    provincia: str | None,
    override: float | None,
) -> tuple[float, str]:
    """IIBB perception by province. 0 if the question has no provincia / IIBB rate."""
    base = iva_base(cif, die, te, extra)
    if override is not None:
        amount = base * (override / 100)
        where = f"provincia {provincia}" if provincia else "pregunta"
        return amount, (
            f"IIBB {override:g}% ({where}) sobre CIF+DIE+estadística+medidas "
            f"({base:g} USD) = {amount:g} USD"
        )
    if provincia is None:
        return 0.0, "IIBB 0 USD (falta provincia; no se usa un % nacional)"
    if not provincia:
        return 0.0, "IIBB 0 USD (provincia no reconocida)"
    rate = IIBB_RATES.get(provincia)
    if rate is None:
        return 0.0, f"IIBB 0 USD (sin alícuota cargada para {provincia})"
    amount = base * (rate / 100)
    return amount, (
        f"IIBB {rate:g}% ({provincia}, alícuota general estimada SIRPEI; "
        f"no es el factor del CUIT) sobre CIF+DIE+estadística+medidas "
        f"({base:g} USD) = {amount:g} USD"
    )


def calc_duty(state: GraphState) -> dict:
    question = state.get("question") or ""
    cif = parse_cif(question)
    if cif is None:
        print("no CIF in question, skip duty")
        return {"impuestos_estimados": 0}
    aec = state.get("ncm_aec") or 0
    die = cif * (aec / 100)
    origen = parse_origen(question)
    qty = parse_cantidad(question)
    inscripto = parse_inscripto(question)
    aec_flag = (state.get("ncm_aec_flag") or "").strip().upper()
    iva_rate, iva_source = iva_rate_for(question, aec_flag)
    provincia = parse_provincia(question)
    iibb_override = parse_iibb_rate(question)
    te, te_line = calc_estadistica(cif, origen)
    extra = 0.0
    lines = [
        f"CIF {cif:g} USD (ingresado por el usuario)",
        f"DIE {aec:g}% sobre CIF = {die:g} USD",
        te_line,
    ]
    if origen:
        lines.append(f"Origen {origen}")
    if qty:
        lines.append(f"Cantidad {qty[0]:g} {qty[1]}")
    if provincia:
        lines.append(f"Provincia {provincia}")
    if inscripto:
        lines.append("Importador responsable inscripto")
    elif re.search(r"consumo\s+particular|uso\s+particular|consumidor\s+final", question, re.I):
        lines.append("Importador uso o consumo particular")
    else:
        lines.append("Importador monotributista (default; si es responsable inscripto, aclararlo)")
    for medida in state.get("ncm_medidas") or []:
        text = medida.get("medida") or ""
        kind = medida.get("kind") or ""
        lines.append(
            f"Medida {medida.get('producto') or '-'} / {medida.get('origen') or '-'}: "
            f"{text}"
        )
        if not origen:
            lines.append("No se aplicó: falta origen en la pregunta.")
            continue
        listed = medida.get("origen") or ""
        if not origin_matches(origen, listed):
            lines.append(f"No aplica a origen {origen}.")
            continue
        rate = rate_for_origin(text, listed, origen)
        applied = False
        if rate is not None:
            amount = cif * (rate / 100)
            extra += amount
            applied = True
            lines.append(
                f"Antidumping ad valorem {rate:g}% sobre CIF = {amount:g} USD"
            )
        spec = specific_for_origin(text, listed, origen)
        if spec:
            if not qty:
                lines.append(
                    f"Derecho específico {spec['usd']:g} USD/{spec['unit']}: "
                    "falta cantidad en la pregunta."
                )
            elif qty[1] != spec["unit"]:
                lines.append(
                    f"Derecho específico {spec['usd']:g} USD/{spec['unit']}: "
                    f"la cantidad está en {qty[1]}, no en {spec['unit']}."
                )
            else:
                amount = qty[0] * spec["usd"]
                extra += amount
                applied = True
                lines.append(
                    f"Derecho específico {qty[0]:g} × {spec['usd']:g} USD/"
                    f"{spec['unit']} = {amount:g} USD"
                )
        elif kind == "min_fob":
            lines.append("Valor mínimo FOB: no es un derecho; no se liquidó.")
        elif kind in {"especifico", "combinada"} and not spec:
            lines.append(
                "Hay derecho específico ambiguo (varias tarifas); no se liquidó."
            )
        elif not applied:
            lines.append("La medida no se liquidó.")
    if aec_flag == "BK":
        lines.append("NCM BK (bien de capital; no es un derecho extra)")
    elif aec_flag == "BIT":
        lines.append(
            "NCM BIT (bien de informática/telecomunicaciones; no es un derecho extra)"
        )
    iva, iva_line = calc_iva(cif, die, te, extra, iva_rate, iva_source)
    perc_iva, perc_iva_line = calc_iva_percepcion(cif, die, te, extra, iva_rate)
    gcias, gcias_line = calc_ganancias(cif, die, te, extra, question, inscripto)
    iibb, iibb_line = calc_iibb(cif, die, te, extra, provincia, iibb_override)
    lines.append(iva_line)
    lines.append(perc_iva_line)
    if inscripto and perc_iva:
        lines.append("La percepción IVA es crédito fiscal para el inscripto.")
    lines.append(gcias_line)
    lines.append(iibb_line)
    total = die + extra + te + iva + perc_iva + gcias + iibb
    print(
        "DUTY",
        total,
        "USD",
        f"(DIE {die} + TE {te} + extra {extra} + IVA {iva} "
        f"+ percIVA {perc_iva} + Gcias {gcias} + IIBB {iibb} of CIF {cif})",
    )
    print("LANDED", cif + total, "USD")
    return {
        "impuestos_estimados": total,
        "cif": cif,
        "origen": origen or "",
        "cantidad": qty[0] if qty else 0.0,
        "unidad": qty[1] if qty else "",
        "inscripto": inscripto,
        "provincia": provincia or "",
        "iva": iva,
        "iva_percepcion": perc_iva,
        "ganancias": gcias,
        "iibb": iibb,
        "costos_asociados": "\n".join(lines),
    }
