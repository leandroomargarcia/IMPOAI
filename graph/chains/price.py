from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from llm import llm

class PriceChoice(BaseModel):
    price: float = Field(description="Unit price as a number, e.g. 4.50")
    currency: str = Field(description="ISO code, usually USD")
    motive: str

price_chain = ChatPromptTemplate.from_messages(
    [
        ("system", "Extract ONE unit price from the hits. Do not invent a number."),
        ("human", "Product:\n{question}\n\nNCM:\n{card}\n\nHits:\n{hits}"),
    ]
) | llm.with_structured_output(PriceChoice, method="function_calling")
