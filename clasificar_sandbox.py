# 0 BOOTSTRAP
# Load secrets, the NCM catalog JSON, and the chat model.
# Used to open the office: nothing is classified here.
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from pydantic import BaseModel, Field

from ncm.catalog import NcmCatalog

load_dotenv()
catalog = NcmCatalog.from_json()
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
tavily = TavilySearch(max_results=5)

# 1 FORMS
# The exact fields the model must return (chapter, heading, 8-digit item, yes/no grade).
# Used so the AI cannot answer in free prose; each thinking box gets a form.

class ChapterChoice(BaseModel):
    chapter: str = Field(description="2 digits, e.g. 01 or 09")
    motive: str

class HeadingChoice(BaseModel):
    heading: str = Field(description="e.g. 09.01")
    motive: str

class ItemChoice(BaseModel):
    item: str = Field(description="8 digits, e.g. 0901.11.10")
    motive: str

class GradeChoice(BaseModel):
    is_valid: bool
    motive: str

class PriceChoice(BaseModel):
    price: float = Field(description="Unit price as a number, e.g. 100.00")
    currency: str = Field(description="Currency code, e.g. USD or EUR")
    motive: str

# 2 AI QUESTIONS
# The four prompts: pick chapter, pick heading, pick item, does this item match the product.
# Used as reusable questions. Still no order: they are not the canvas yet.
router = ChatPromptTemplate.from_messages(
    [
        ("system", "Pick ONE chapter from the list. Titles are indicative. \n\nRGI:\n{rgi}"),
        ("human",  "Product:\n{question}\n\nChapter:\n{chapters}"),
    ]
) | llm.with_structured_output(ChapterChoice, method="function_calling")

pick_heading = ChatPromptTemplate.from_messages(
    [
        ("system", "Pick ONE heading. Use the notes. Do not invent codes.\n\nRGI:\n{rgi}"),
        ("human",  "Product:\n{question}\n\nNotes:\n{notes}\n\nHeadings:\n{headings}"),
    ]
) | llm.with_structured_output(HeadingChoice, method="function_calling")

pick_item = ChatPromptTemplate.from_messages(
    [
        ("system",
        "Pick ONE 8-digit item from the list. "
        "Use 'other' only if no more specific item fits.\n\nRGI:\n{rgi}"),
        ("human", "Product:\n{question}\n\nNotes:\n{notes}\n\nItems:\n{items}"),
    ]
) | llm.with_structured_output(ItemChoice, method="function_calling")

grader = ChatPromptTemplate.from_messages(
    [
        (
            "system", 
            "Does this item cover the product?\n"
            "False if the notes exclude it or the description does not match.\n\nRGI:\n{rgi}"
        ),
        ("human", "Product:\n{question}\n\nNotes:\n{notes}\n\nItem:\n{item}\n\nCard:\n{card}"),
    ]
) | llm.with_structured_output(GradeChoice, method="function_calling")

pick_price = ChatPromptTemplate.from_messages(
    [
        ("system", "Extract ONE unit price from the hits. Do not invent a number.\n\n"),
        ("human", "Product:\n{question}\n\nNCM:\n{card}\n\nHits:\n{hits}"),
    ]
) | llm.with_structured_output(PriceChoice, method="function_calling")

# 3 CANVAS WALK
# Walk the boxes in order: chapter → notes → heading → item → code exists? → product match?
# If it fails, go back to chapter (max 3 tries).
# Used to run YOUR architecture. This drawer IS the left-hand NCM branch.

def classify(question: str) -> None:
    for attempt in range(1, 4):
        print(f"Attempt {attempt}:")

        caps = catalog.search_chapters(question)
        list_caps = "\n".join(f"- {c['chapter']}: {c['title']}" for c in caps)
        cap = router.invoke({"rgi": catalog.rgi, "question": question, "chapters": list_caps})
        print("chapter", cap.chapter, "-", cap.motive)

        chapter = cap.chapter.zfill(2)
        notes = catalog.get_notes(chapter)
        notes_text = (
            f"{notes['title']}\n"
            f"{notes['chapter_notes']}\n"
            f"{notes['section_notes']}"
        )
        print("notes loaded")
        print(notes_text)

        headings = catalog.list_headings(chapter)
        list_headings = "\n".join(f"- {h['heading']}: {h['description']}" for h in headings)
        heading = pick_heading.invoke({"rgi": catalog.rgi, "question": question, "notes": notes_text, "headings": list_headings})
        print("heading", heading.heading, "-", heading.motive)

        items = catalog.list_items(heading.heading)
        list_items = "\n".join(
            f"- {i['ncm']} | AEC {i['aec']} | {i['full_description']}" for i in items
        )
        item = pick_item.invoke(
            {
                "rgi": catalog.rgi,
                "question": question,
                "notes": notes_text,
                "items": list_items,
            }
        )
        print("item", item.item, "-", item.motive)

        card = catalog.get_ncm(item.item)
        if not card:
            print("code not in catalog:", item.item)
            continue
        print("card OK", card["codigo"], "AEC", card["aec"])
        print(card["descripcion_completa"])

        grade = grader.invoke(
            {
                "rgi": catalog.rgi,
                "question": question,
                "notes": notes_text,
                "item": item.item,
                "card": f"{card['codigo']} | {card['descripcion_completa']}",
            }
        )
        if not grade.is_valid:
            print("rejected:", grade.motive)
            continue

        print("DONE", card["codigo"], "AEC", card["aec"])
        return card
    print("FAILED after 3 attempts")
    return None

# 4 PLAY BUTTON
# The sample product string to classify (e.g. green coffee beans).
# Used to start one run and print the result.
if __name__ == "__main__":
    question = "green coffee beans"
    card = classify(question)
    if not card:
        print("no card, skip price")
    else:
        query = f"FOB unit price {card['descripcion_completa']}"
        raw = tavily.invoke({"query": query})
        hits = raw.get("results") or []
        hits_text = "\n".join(
            f"- {h.get('title')}: {h.get('content')}" for h in hits if h.get("content")
        )
        quote = pick_price.invoke(
            {
                "question": question,
                "card": f"{card['codigo']} | {card['descripcion_completa']}",
                "hits": hits_text or "(no hits)",
            }
        )
        print("PRICE", quote.price, quote.currency, "-", quote.motive)

        aec = card["aec"] or 0
        duty = quote.price * (aec / 100)
        print("DUTY", duty, quote.currency, f"(AEC {aec}%)")
        print("LANDED", quote.price + duty, quote.currency)