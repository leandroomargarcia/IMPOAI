"""Office as a LangChain tool. The chat LLM decides when to call it."""

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from api.guardrails import Slots, is_ready, missing_prompt, pack_question
from api.office import invoke_office, public_result

TOOL_NAME = "classify_ncm"


class ClassifyArgs(BaseModel):
    product: str = Field(
        default="",
        description="Producto a importar. Vacío si ya está en el historial.",
    )
    cif_usd: float | None = Field(
        default=None,
        description="CIF en USD. Omití si ya está en el historial.",
    )
    origen: str = Field(default="", description="País de origen, si se conoce.")
    provincia: str = Field(
        default="",
        description="Provincia argentina para IIBB, si se conoce.",
    )
    inscripto: bool = Field(
        default=False,
        description="True solo si el importador es responsable inscripto.",
    )


def merge_slots(args: dict, slots: Slots) -> Slots:
    product = (args.get("product") or slots.product or "").strip()
    # CIF only from user turns (parse_cif → slots). Never trust tool-invented cif_usd.
    cif = slots.cif
    origen = (args.get("origen") or slots.origen or "").strip()
    provincia = (args.get("provincia") or slots.provincia or "").strip()
    inscripto = bool(args.get("inscripto") or slots.inscripto)
    extras = slots.extras
    return Slots(
        product=product or None,
        cif=cif,
        origen=origen or None,
        provincia=provincia or None,
        inscripto=inscripto,
        extras=extras,
    )


def run_classify(args: dict, slots: Slots) -> dict:
    merged = merge_slots(args, slots)
    if not is_ready(merged):
        return {"error": missing_prompt(merged)}
    out = invoke_office(pack_question(merged), ["chat"])
    pub = public_result(out)
    pub["_slots"] = merged
    return pub


def _schema_stub(
    product: str = "",
    cif_usd: float | None = None,
    origen: str = "",
    provincia: str = "",
    inscripto: bool = False,
) -> str:
    return ""


CLASSIFY_TOOL = StructuredTool.from_function(
    func=_schema_stub,
    name=TOOL_NAME,
    description=(
        "Clasifica la mercadería en NCM (posición / partida arancelaria) "
        "y estima la liquidación fiscal argentina (DIE, IVA, percepciones, IIBB). "
        "Llamá esta herramienta cuando el usuario pida clasificar, la posición, "
        "la partida, el NCM o liquidar / estimar derechos. "
        "No la uses para explicar qué es el NCM o una posición arancelaria. "
        "Hace falta producto y el CIF en USD que el usuario escribió para "
        "ESE producto. Si cambió de mercadería, el CIF anterior no vale. "
        "No inventes cif_usd."
    ),
    args_schema=ClassifyArgs,
)
