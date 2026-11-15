"""
The web app: a FastAPI server around the pipeline in rag.py.

Run:   uvicorn app:app --reload
Open:  http://localhost:8000        (web page)
       http://localhost:8000/docs   (interactive API docs)
"""
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from google.genai import errors as gemini_errors
from pydantic import BaseModel, Field

import rag
from config import LLM_MODEL, MAX_UPLOAD_MB

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="RAG PDF", description="Upload PDFs and ask questions about them.")


# ---------------------------- Schemas ----------------------------
class Document(BaseModel):
    doc_id: str
    name: str
    pages: int
    chunks: int


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    doc_id: str | None = Field(
        default=None, description="Search only this document. Omit to search all."
    )


class Source(BaseModel):
    doc_id: str
    name: str
    page: int
    text: str


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]


# ---------------------------- Routes -----------------------------
# Routes are plain `def` (not `async def`) on purpose: embedding and the
# Gemini call are blocking, and FastAPI runs `def` routes in a thread pool
# so one slow request does not freeze the server.

@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "llm_model": LLM_MODEL, "gemini_key_set": rag.llm is not None}


@app.post("/documents", response_model=Document, status_code=201)
def upload_document(file: UploadFile = File(...)):
    """Upload a PDF and index it."""
    limit = MAX_UPLOAD_MB * 1024 * 1024
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"File is larger than {MAX_UPLOAD_MB} MB.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "This is not a PDF file.")
    try:
        return rag.index_document(data, Path(file.filename or "document.pdf").name)
    except rag.RagError as e:
        raise HTTPException(400, str(e))


@app.get("/documents", response_model=list[Document])
def list_documents():
    """List every indexed document."""
    return rag.list_documents()


@app.delete("/documents/{doc_id}", status_code=204)
def delete_document(doc_id: str):
    """Remove a document from the index."""
    if not rag.delete_document(doc_id):
        raise HTTPException(404, "Document not found.")


@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest):
    """Answer a question from one document (doc_id) or from all of them."""
    try:
        text, hits = rag.answer(body.question.strip(), body.doc_id)
    except rag.RagError as e:
        raise HTTPException(400, str(e))
    except gemini_errors.APIError as e:
        raise HTTPException(502, f"Gemini error: {e.message or e}")
    return {
        "answer": text,
        "sources": [
            {"doc_id": m["doc_id"], "name": m["source"], "page": m["page"], "text": t}
            for t, m in hits
        ],
    }
