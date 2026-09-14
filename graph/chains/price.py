from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from llm import llm

class PriceChoice(BaseModel):
    price: float = Field(description="Argentine selling price as a number, e.g. 4500")
    currency: str = Field(description="ISO code, usually ARS or USD")
    motive: str

price_chain = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Extract ONE Argentine market selling price (wholesale or retail). "
            "This is not FOB and not an import cost. "
            "Do not invent a number. If the hits have no price, use 0.",
        ),
        ("human", "Product:\n{question}\n\nNCM:\n{card}\n\nHits:\n{hits}"),
    ]
) | llm.with_structured_output(PriceChoice, method="function_calling")
