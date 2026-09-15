from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from llm import llm

class ChapterChoice(BaseModel):
    chapter: str = Field(description="2 digits, e.g. 01 or 09")
    motive: str

class HeadingChoice(BaseModel):
    heading: str = Field(description="e.g. 09.01")
    motive: str

class SubheadingChoice(BaseModel):
    subheading: str = Field(description="6 digits, e.g. 0901.11")
    motive: str

class ItemChoice(BaseModel):
    item: str = Field(description="8 digits, e.g. 0901.11.10")
    motive: str

class GradeChoice(BaseModel):
    is_valid: bool
    motive: str

router = ChatPromptTemplate.from_messages(
    [
        ("system", "Pick ONE chapter from the list. Titles are indicative. \n\nRGI:\n{rgi}"),
        ("human",  "Product:\n{question}\n\nChapter:\n{chapters}"),
    ]
) | llm.with_structured_output(ChapterChoice, method="function_calling")

heading_chain = ChatPromptTemplate.from_messages(
    [
        ("system", "Pick ONE heading. Use the notes. Do not invent codes.\n\nRGI:\n{rgi}"),
        ("human",  "Product:\n{question}\n\nNotes:\n{notes}\n\nHeadings:\n{headings}"),
    ]
) | llm.with_structured_output(HeadingChoice, method="function_calling")

subheading_chain = ChatPromptTemplate.from_messages(
    [
        ("system", "Pick ONE 6-digit subheading. Do not invent codes.\n\nRGI:\n{rgi}"),
        ("human", "Product:\n{question}\n\nNotes:\n{notes}\n\nSubheadings:\n{subheadings}"),
    ]
) | llm.with_structured_output(SubheadingChoice, method="function_calling")

item_chain = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Pick ONE 8-digit item from the list. "
            "Use 'other' only if no more specific item fits.\n\nRGI:\n{rgi}",
        ),
        ("human", "Product:\n{question}\n\nNotes:\n{notes}\n\nItems:\n{items}"),
    ]
) | llm.with_structured_output(ItemChoice, method="function_calling")

grade_chain = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Does this item cover the product?\n"
            "False if the notes exclude it or the description does not match.\n\nRGI:\n{rgi}",
        ),
        ("human", "Product:\n{question}\n\nNotes:\n{notes}\n\nItem:\n{item}\n\nCard:\n{card}"),
    ]
) | llm.with_structured_output(GradeChoice, method="function_calling")
