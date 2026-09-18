import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()
llm = ChatOpenAI(
    model=os.getenv("IMPOAI_MODEL", "gpt-4.1-mini"),
    temperature=0,
)