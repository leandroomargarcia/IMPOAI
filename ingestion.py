from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

PERSIST_DIR = "./.chroma"
NCM_COLLECTION = "impoai-ncm"
NCM_PDF_PATH = Path(__file__).resolve().parent / "nomenclatura_comun_del_mercosur_ncm.pdf"

embeddings = OpenAIEmbeddings()

retriever_ncm = Chroma(
    collection_name=NCM_COLLECTION,
    persist_directory=PERSIST_DIR,
    embedding_function=embeddings,
).as_retriever()


def _reset_collection(name: str) -> None:
    store = Chroma(
        collection_name=name,
        persist_directory=PERSIST_DIR,
        embedding_function=embeddings,
    )
    store.delete_collection()


if __name__ == "__main__":
    if not NCM_PDF_PATH.exists():
        raise FileNotFoundError(f"No está el PDF del NCM: {NCM_PDF_PATH}")

    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=1000,
        chunk_overlap=150,
    )

    docs_ncm = PyPDFLoader(str(NCM_PDF_PATH)).load()
    splits_ncm = text_splitter.split_documents(docs_ncm)
    print(f"NCM: {len(docs_ncm)} paginas -> {len(splits_ncm)} chunks")

    _reset_collection(NCM_COLLECTION)
    Chroma.from_documents(
        documents=splits_ncm,
        collection_name=NCM_COLLECTION,
        embedding=embeddings,
        persist_directory=PERSIST_DIR,
    )
    print(f"Indexado en collection '{NCM_COLLECTION}'")
