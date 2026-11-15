"""
The RAG pipeline. Used two ways:

    python rag.py path/to/document.pdf     # terminal chat with one PDF
    import rag                             # from the web app (app.py)

Flow:  PDF -> text -> chunks -> embeddings -> vector DB
       question -> embedding -> top matching chunks -> Gemini -> answer

Settings live in config.py (read from environment variables / .env).
"""
import hashlib
import io
import os
import sys

import chromadb
from google import genai
from google.genai import types
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from config import (
    CHROMA_PATH,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    COLLECTION_NAME,
    EMBED_MODEL,
    GEMINI_API_KEY,
    LLM_MODEL,
    TOP_K,
)

SYSTEM_PROMPT = (
    "Answer using ONLY the context provided. "
    "Cite page numbers like (p. 3). If the answer isn't "
    "in the context, say you don't know."
)

embedder = SentenceTransformer(EMBED_MODEL)
db = chromadb.PersistentClient(path=CHROMA_PATH)   # saved to disk
collection = db.get_or_create_collection(COLLECTION_NAME)
llm = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


class RagError(Exception):
    """A problem the user can fix (bad PDF, missing key, nothing indexed)."""


# ---------------------------- 1. Load ----------------------------
def load_pdf(data):
    """Return a list of (page_number, text) for pages that have text."""
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append((i + 1, text))
    except Exception as e:
        raise RagError(f"Could not read this file as a PDF: {e}") from e
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
def index_document(data, name):
    """Index a PDF given its bytes and a display name. Returns its summary.

    The document id is a hash of the file contents, so the same file always
    gets the same id no matter what it is called or where it is stored.
    """
    doc_id = hashlib.sha256(data).hexdigest()[:16]
    pages = load_pdf(data)
    chunks = chunk_pages(pages)
    if not chunks:
        raise RagError("No text found. Is this a scanned PDF? (needs OCR)")

    texts = [c["text"] for c in chunks]
    vectors = embedder.encode(texts).tolist()

    # Remove any earlier copy first so no stale chunks are left behind.
    collection.delete(where={"doc_id": doc_id})
    collection.add(
        ids=[f"{doc_id}-{i}" for i in range(len(chunks))],
        documents=texts,
        embeddings=vectors,
        metadatas=[
            {"doc_id": doc_id, "source": name, "page": c["page"]} for c in chunks
        ],
    )
    return {"doc_id": doc_id, "name": name, "pages": len(pages), "chunks": len(chunks)}


def list_documents():
    """Return one summary per indexed document."""
    docs = {}
    for meta in collection.get(include=["metadatas"])["metadatas"]:
        doc_id = meta.get("doc_id")
        if not doc_id:
            continue
        doc = docs.setdefault(
            doc_id, {"doc_id": doc_id, "name": meta["source"], "pages": set(), "chunks": 0}
        )
        doc["pages"].add(meta["page"])
        doc["chunks"] += 1
    return sorted(
        ({**d, "pages": len(d["pages"])} for d in docs.values()),
        key=lambda d: d["name"].lower(),
    )


def delete_document(doc_id):
    """Remove a document's chunks. Returns False if it was not indexed."""
    if not collection.get(where={"doc_id": doc_id}, limit=1)["ids"]:
        return False
    collection.delete(where={"doc_id": doc_id})
    return True


# ---------------------------- 4. Retrieve ------------------------
def retrieve(question, doc_id=None):
    """Return the TOP_K closest chunks, from one document or from all."""
    q_vector = embedder.encode(question).tolist()
    results = collection.query(
        query_embeddings=[q_vector],
        n_results=TOP_K,
        where={"doc_id": doc_id} if doc_id else None,
    )
    return list(zip(results["documents"][0], results["metadatas"][0]))


# ---------------------------- 5. Generate ------------------------
def answer(question, doc_id=None):
    """Return (answer_text, hits). hits is a list of (chunk_text, metadata)."""
    if llm is None:
        raise RagError("GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.")

    hits = retrieve(question, doc_id)
    if not hits:
        raise RagError("Nothing to search. Upload a PDF first.")

    context = "\n\n".join(
        f"[{meta['source']}, page {meta['page']}]\n{text}" for text, meta in hits
    )
    response = llm.models.generate_content(
        model=LLM_MODEL,
        contents=f"Context:\n{context}\n\nQuestion: {question}",
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )
    return response.text or "(Gemini returned no text.)", hits


# ---------------------------- Main loop --------------------------
if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python rag.py path/to/document.pdf")
    if llm is None:
        sys.exit("GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.")

    path = sys.argv[1]
    try:
        with open(path, "rb") as f:
            doc = index_document(f.read(), os.path.basename(path))
    except (OSError, RagError) as e:
        sys.exit(str(e))
    print(f"Indexed {doc['chunks']} chunks from {doc['pages']} pages.")

    while True:
        q = input("\nAsk a question (or 'exit'): ").strip()
        if q.lower() in {"exit", "quit"}:
            break
        if not q:
            continue
        reply, sources = answer(q, doc["doc_id"])
        print("\n" + reply)
        print("\nSources: " + ", ".join(f"p.{m['page']}" for _, m in sources))
