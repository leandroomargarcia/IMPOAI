from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()

def format_hab_sources(docs) -> str:
    lines = []
    for i, doc in enumerate(docs or [], start=1):
        title = (doc.metadata or {}).get("title") or "(sin título)"
        url = (doc.metadata or {}).get("url") or ""
        lines.append(f"[{i}] {title}\nURL: {url}\n{doc.page_content}")
    return "\n\n".join(lines)

class Requisito(BaseModel):
    texto: str = Field(description="Requisito de habilitación, en una frase")
    source_ids: list[int] = Field(
        description="Indices [n] de las fuentes que lo respaldan. Mínimo uno."
    )


class HabAnalisis(BaseModel):
    requisitos: list[Requisito]
    resumen: str = Field(description="Resumen de los requisitos corto; sin URLs")

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
structured = llm.with_structured_output(HabAnalisis, method="function_calling")

system = """Sos analista de habilitaciones de importación en Argentina.
Usá SOLO las fuentes numeradas (deben ser oficiales: .gob.ar / organismo competente).
Cada requisito debe tener source_ids que existan en esas fuentes (1, 2, 3...).
No inventes organismos ni trámites.
No escribas URLs: solo los números de fuente.
Ignorá tiendas, marketplaces y catálogos (Mercado Libre, Accio, Amazon, etc.).
No tomes certificaciones comerciales (EEC, CE, ISO de un vendedor) como trámite argentino.
No atribuyas ANMAT, SENASA u otro organismo salvo que las fuentes vinculen ese trámite a ESTE tipo de producto (no a otro).
Si las fuentes no aplican, devolvés requisitos vacío y en el resumen lo decís."""

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system),
        ("human", "Consulta del importador:\n{question}\n\nFuentes:\n{sources}"),
    ]
)

analista_hab_chain = prompt | structured