"""CIF / slot checks for /run and /chat. Does not classify."""

from __future__ import annotations

import re
from dataclasses import dataclass

from graph.nodes.calculate_costs import (
    INSCRIPTO_NO_RE,
    INSCRIPTO_YES_RE,
    IVA_EXENTO_RE,
    IVA_RATE_RE,
    parse_cantidad,
    parse_cif,
    parse_iibb_rate,
    parse_inscripto,
    parse_origen,
    parse_provincia,
    strip_cif_clause,
)

CIF_REQUIRED = "CIF required (e.g. CIF 80000 USD)"

_JAIL = re.compile(
    r"ignore (all )?(previous|above) instructions|jailbreak"
    r"|revel[aá]\s+(el\s+)?system prompt",
    re.I,
)
_CLASSIFY = re.compile(
    r"\b("
    r"clasific\w*"
    r"|liquid\w*"
    r"|estim[aeáé]\w*\s+(los\s+)?(derechos|impuestos|aranceles|costos)"
    r"|dame\s+(el\s+|la\s+)?(ncm|posici[oó]n|partida)"
    r"|decime\s+(el\s+|la\s+)?(ncm|posici[oó]n|partida)"
    r"|pasame\s+(el\s+|la\s+)?(ncm|posici[oó]n|partida)"
    r"|c[oó]digo\s+ncm"
    r"|posici[oó]n(es)?(\s+arancelaria)?"
    r"|partida(s)?(\s+arancelaria)?"
    r"|corr[eé]\s+el\s+(office|grafo|workflow)"
    r"|cu[aá]nto\s+(pago|sale|cuesta)\s+import"
    r")\b",
    re.I,
)
_CLASSIFY_FAQ = re.compile(
    r"^\s*qu[eé]\s+(es|significa)\s+(una\s+|la\s+)?"
    r"(posici[oó]n(\s+arancelaria)?|partida(\s+arancelaria)?|ncm)\s*\??\s*$",
    re.I,
)
_CLASSIFY_NOISE = re.compile(
    r"\b("
    r"clasific\w*|liquid\w*|por\s+favor|quiero\s+que|podr[ií]as"
    r"|posici[oó]n(es)?(\s+arancelaria)?|partida(s)?(\s+arancelaria)?"
    r"|dame|decime|pasame|cu[aá]l\s+es\s+(el|la)"
    r")\b",
    re.I,
)
_QUESTION = re.compile(
    r"^\s*(qu[eé]|c[oó]mo|cu[aá]l|qui[eé]n|por\s+qu[eé]|expli)"
    r"|\?\s*$",
    re.I,
)


@dataclass
class Slots:
    product: str | None = None
    cif: float | None = None
    origen: str | None = None
    provincia: str | None = None
    inscripto: bool = False
    extras: str = ""


_CIF_NUM = r"(\d{1,3}(?:\.\d{3})+|\d+(?:[.,]\d+)?)"
_CIF_USER = re.compile(rf"\bcif\s*(?:es|de|por|:|=)?\s*{_CIF_NUM}", re.I)
_CIF_BARE = re.compile(rf"^\s*(?:usd\s*)?{_CIF_NUM}(?:\s*usd)?\s*$", re.I)


def _cif_to_float(raw: str) -> float:
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
        return float(raw.replace(".", ""))
    return float(raw.replace(",", "."))


def parse_user_cif(text: str) -> float | None:
    """Chat CIF: 'CIF 80.000', 'cif es 5000', or a bare '80000 USD'."""
    match = _CIF_USER.search(text or "")
    if match:
        return _cif_to_float(match.group(1))
    bare = _CIF_BARE.fullmatch((text or "").strip())
    if bare:
        return _cif_to_float(bare.group(1))
    return parse_cif(text)


def require_cif(question: str) -> str | None:
    if parse_cif(question) is None:
        return CIF_REQUIRED
    return None


def is_jailbreak(text: str) -> bool:
    return bool(_JAIL.search(text or ""))


def wants_classify(text: str) -> bool:
    raw = text or ""
    if _CLASSIFY_FAQ.search(raw.strip()):
        return False
    return bool(_CLASSIFY.search(raw))


def is_general_question(text: str) -> bool:
    return bool(_QUESTION.search((text or "").strip()))


def _norm_product(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def products_differ(old: str | None, new: str | None) -> bool:
    """True if new looks like another good, not an elaboration of the old one."""
    a, b = _norm_product(old or ""), _norm_product(new or "")
    if not a or not b or a == b:
        return False
    if a in b or b in a:
        return False
    return True


def extra_clauses(text: str) -> str:
    bits: list[str] = []
    qty = parse_cantidad(text)
    if qty:
        bits.append(f"{qty[0]:g} {qty[1]}")
    if IVA_EXENTO_RE.search(text or ""):
        bits.append("IVA exento")
    else:
        match = IVA_RATE_RE.search(text or "")
        if match:
            bits.append(f"IVA {match.group(1)}")
    iibb = parse_iibb_rate(text)
    if iibb is not None:
        bits.append(f"IIBB {iibb:g}")
    return " ".join(bits)


def update_slots(slots: Slots, text: str) -> Slots:
    incoming_cif = parse_user_cif(text)
    if incoming_cif is not None:
        slots.cif = incoming_cif
    origen = parse_origen(text)
    if origen:
        slots.origen = origen
    provincia = parse_provincia(text)
    if provincia:
        slots.provincia = provincia
    if INSCRIPTO_NO_RE.search(text or "") or INSCRIPTO_YES_RE.search(text or ""):
        slots.inscripto = parse_inscripto(text)
    cleaned = _CLASSIFY_NOISE.sub(" ", text or "")
    product = strip_cif_clause(cleaned)
    if len(product) >= 3 and (
        wants_classify(text) or not is_general_question(cleaned)
    ):
        if slots.product and products_differ(slots.product, product):
            if incoming_cif is None:
                slots.cif = None
            slots.extras = ""
        slots.product = product
    extra = extra_clauses(text)
    if extra:
        slots.extras = extra
    return slots


def is_ready(slots: Slots) -> bool:
    return bool(slots.product) and slots.cif is not None


def pack_question(slots: Slots) -> str:
    bits = [slots.product or ""]
    if slots.cif is not None:
        bits.append(f"CIF {slots.cif:g} USD")
    if slots.origen:
        bits.append(f"origen {slots.origen}")
    if slots.provincia:
        bits.append(f"provincia {slots.provincia}")
    if slots.inscripto:
        bits.append("responsable inscripto")
    if slots.extras:
        bits.append(slots.extras)
    return " ".join(bit for bit in bits if bit)


def missing_prompt(slots: Slots) -> str:
    if not slots.product:
        return (
            "Para clasificar necesito el producto y el CIF en USD. "
            "¿Qué vas a importar y a qué valor CIF?"
        )
    return (
        f"Para clasificar «{slots.product}» necesito el CIF en USD. "
        "Si sos responsable inscripto o hay provincia para IIBB, decime también."
    )


def slots_hint(slots: Slots) -> str:
    bits = []
    if slots.product:
        bits.append(f"producto={slots.product}")
    if slots.cif is not None:
        bits.append(f"CIF={slots.cif:g}")
    if slots.origen:
        bits.append(f"origen={slots.origen}")
    if slots.provincia:
        bits.append(f"provincia={slots.provincia}")
    memory = ", ".join(bits) if bits else "sin producto/CIF aún"
    extra = ""
    if slots.cif is None:
        extra = (
            " Este producto no tiene CIF propio. Si piden clasificar NCM / "
            "posición, pedí el CIF en USD de ESTA mercadería; no llames "
            "classify_ncm y no reutilices el CIF de un producto anterior."
        )
    return (
        f"Slots en memoria: {memory}. "
        "Respondé la pregunta. No inventes un NCM de 8 dígitos como "
        "clasificación oficial."
        f"{extra}"
    )
