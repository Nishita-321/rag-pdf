"""
Step 1: A minimal RAG pipeline as a plain script (no web app yet).

Usage:
    python rag.py path/to/document.pdf

Flow:  PDF -> text -> chunks -> embeddings -> vector DB
       question -> embedding -> top matching chunks -> LLM -> answer
"""
import sys

import chromadb
import ollama
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

# ---- Settings (later these move into a config / Kubernetes ConfigMap) ----
EMBED_MODEL = "all-MiniLM-L6-v2"   # small, fast, free embedding model
LLM_MODEL = "llama3.2"             # any model you've pulled with Ollama
CHUNK_SIZE = 800                   # characters per chunk
CHUNK_OVERLAP = 150                # overlap so sentences aren't cut in half
TOP_K = 4                          # how many chunks to give the LLM

embedder = SentenceTransformer(EMBED_MODEL)
db = chromadb.PersistentClient(path="./chroma_db")   # saved to disk
collection = db.get_or_create_collection("documents")


# ---------------------------- 1. Load ----------------------------
def load_pdf(path):
    """Return a list of (page_number, text) for pages that have text."""
    reader = PdfReader(path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append((i + 1, text))
    return pages


# ---------------------------- 2. Chunk ---------------------------
def chunk_pages(pages):
    """Split each page into overlapping chunks, remembering the page number."""
    chunks = []
    step = CHUNK_SIZE - CHUNK_OVERLAP
    for page_num, text in pages:
        for start in range(0, len(text), step):
            piece = text[start:start + CHUNK_SIZE].strip()
            if piece:
                chunks.append({"text": piece, "page": page_num})
    return chunks


# ---------------------------- 3. Index ---------------------------
def index_document(path):
    pages = load_pdf(path)
    chunks = chunk_pages(pages)
    if not chunks:
        sys.exit("No text found. Is this a scanned PDF? (needs OCR)")

    texts = [c["text"] for c in chunks]
    vectors = embedder.encode(texts).tolist()

    # upsert + stable ids = re-running on the same file won't duplicate it
    collection.upsert(
        ids=[f"{path}-{i}" for i in range(len(chunks))],
        documents=texts,
        embeddings=vectors,
        metadatas=[{"source": path, "page": c["page"]} for c in chunks],
    )
    print(f"Indexed {len(chunks)} chunks from {len(pages)} pages.")


# ---------------------------- 4. Retrieve ------------------------
def retrieve(question):
    q_vector = embedder.encode(question).tolist()
    results = collection.query(query_embeddings=[q_vector], n_results=TOP_K)
    return list(zip(results["documents"][0], results["metadatas"][0]))


# ---------------------------- 5. Generate ------------------------
def answer(question):
    hits = retrieve(question)
    context = "\n\n".join(
        f"[Page {meta['page']}]\n{text}" for text, meta in hits
    )

    response = ollama.chat(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Answer using ONLY the context provided. "
                    "Cite page numbers like (p. 3). If the answer isn't "
                    "in the context, say you don't know."
                ),
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}",
            },
        ],
    )
    return response["message"]["content"], hits


# ---------------------------- Main loop --------------------------
if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python rag.py path/to/document.pdf")

    index_document(sys.argv[1])

    while True:
        q = input("\nAsk a question (or 'exit'): ").strip()
        if q.lower() in {"exit", "quit"}:
            break
        if not q:
            continue
        reply, sources = answer(q)
        print("\n" + reply)
        print("\nSources: " + ", ".join(f"p.{m['page']}" for _, m in sources))
