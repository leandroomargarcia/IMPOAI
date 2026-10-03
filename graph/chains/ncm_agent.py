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
    is_valid: bool = Field(
        description="True if this 8-digit item covers the product. Notes are exclusions, not an allow-list."
    )
    motive: str

GRADE_SYSTEM = (
    "Does this 8-digit item cover the product?\n"
    "Chapter notes are exclusions (what the chapter does NOT include), "
    "not a catalogue of allowed goods.\n"
    "True if the item/card description fits the product.\n"
    "False only if a note actually excludes THIS product, "
    "or the item/card clearly describes something else.\n"
    "Do not reject because the product name is absent from the notes "
    "or is not spelled out in the item text.\n"
    "If the product states a capacity/size and the item has a numeric limit "
    "that excludes it (e.g. 20 t/h vs superior a 45 t/h), False.\n\n"
    "RGI:\n{rgi}"
)

router = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Pick ONE chapter from the list. Titles are indicative (RGI 1); "
            "heading texts and notes come later.\n\n"
            "Chapters:\n{chapters}",
        ),
        ("human", "Product:\n{question}"),
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
        ("system", GRADE_SYSTEM),
        ("human", "Product:\n{question}\n\nNotes:\n{notes}\n\nItem:\n{item}\n\nCard:\n{card}"),
    ]
) | llm.with_structured_output(GradeChoice, method="function_calling")

class HeadingBeam(BaseModel):
    headings: list[str] = Field(description="Most likely 4-digit headings first, e.g. ['94.03', '44.20']")
    motive: str

class ItemRanking(BaseModel):
    items: list[str] = Field(description="8-digit items from the list, best first, e.g. ['9403.50.00']")
    motive: str

heading_beam_chain = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "List the {beam} most likely 4-digit headings (XX.XX) for the product, most likely first. "
            "Consider every chapter, not only the one suggested by the material. "
            "Use real HS / Mercosur headings; do not invent codes.\n\nChapters:\n{chapters}",
        ),
        ("human", "Product:\n{question}"),
    ]
) | llm.with_structured_output(HeadingBeam, method="function_calling")

rank_chain = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Rank up to {finalists} 8-digit items from the candidate list, best first. "
            "Candidates come from several headings: first decide the heading (RGI 1), "
            "then compare subheadings and items at the same level (RGI 6). "
            "Use 'Los demás' only if no more specific item fits. "
            "Only codes from the list.\n\nRGI:\n{rgi}",
        ),
        ("human", "Product:\n{question}\n\nNotes:\n{notes}\n\nCandidates:\n{candidates}"),
    ]
) | llm.with_structured_output(ItemRanking, method="function_calling")