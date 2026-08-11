import os
import glob
import chromadb
from chromadb.utils import embedding_functions
from pypdf import PdfReader
from app.core.config import settings

def extract_text_from_pdf(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])

def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> list[str]:
    words = text.split()
    return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size - overlap) if words[i:i + chunk_size]]

def build_vector_store():
    chroma_client = chromadb.PersistentClient(path=settings.CHROMA_DB_DIR)
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    collection = chroma_client.get_or_create_collection(
        name="askly_knowledge",
        embedding_function=sentence_transformer_ef
    )

    documents, metadatas, ids = [], [], []
    doc_id_counter = 0

    file_paths = glob.glob(f"{settings.DATA_DIR}/*.txt") + glob.glob(f"{settings.DATA_DIR}/*.md") + glob.glob(f"{settings.DATA_DIR}/*.pdf")

    for file_path in file_paths:
        doc_name = os.path.basename(file_path)
        content = extract_text_from_pdf(file_path) if file_path.endswith(".pdf") else open(file_path, "r", encoding="utf-8").read()

        if not content.strip():
            continue

        chunks = chunk_text(content, chunk_size=300, overlap=50)
        for idx, chunk in enumerate(chunks):
            documents.append(chunk)
            metadatas.append({"source": doc_name, "chunk_index": idx})
            ids.append(f"doc_{doc_id_counter}")
            doc_id_counter += 1

    if documents:
        collection.add(documents=documents, metadatas=metadatas, ids=ids)
        print(f"✅ Successfully indexed {len(documents)} chunks into ChromaDB!")

if __name__ == "__main__":
    build_vector_store()