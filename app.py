"""
The web app: a FastAPI server around the pipeline in rag.py.

Run:   uvicorn app:app --reload
Open:  http://localhost:8000          (web page)
       http://localhost:8000/docs     (interactive API docs)
       http://localhost:8000/metrics  (Prometheus metrics)
"""
import logging
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from google.genai import errors as gemini_errors
from pydantic import BaseModel, Field

import observability as obs

obs.setup_logging()  # before importing rag, so model-loading logs are JSON too

import rag  # noqa: E402
from config import LLM_MODEL, MAX_UPLOAD_MB  # noqa: E402

STATIC_DIR = Path(__file__).parent / "static"
QUIET_PATHS = {"/health", "/metrics"}  # polled constantly; counted but not logged

app = FastAPI(title="RAG PDF", description="Upload PDFs and ask questions about them.")


def refresh_index_gauges():
    """Update the 'documents' and 'chunks' gauges from what is stored."""
    docs = rag.list_documents()
    obs.DOCUMENTS.set(len(docs))
    obs.CHUNKS.set(sum(d["chunks"] for d in docs))


refresh_index_gauges()
obs.log_event("app_started", llm_model=LLM_MODEL, gemini_key_set=rag.llm is not None)


# ---------------------------- Observability ----------------------
@app.middleware("http")
async def observe_request(request: Request, call_next):
    """Give each request an id, time it, count it, and log one line for it."""
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    obs.request_id.set(rid)
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = rid
        return response
    except Exception:
        obs.log_event("unhandled_error", logging.ERROR, exc_info=True,
                      method=request.method, path=request.url.path)
        raise
    finally:
        seconds = time.perf_counter() - start
        # Use the route template ("/documents/{doc_id}"), not the real URL,
        # so metrics do not get a separate series per document.
        route = request.scope.get("route")
        path = route.path if route else "unmatched"
        obs.HTTP_REQUESTS.labels(request.method, path, status).inc()
        obs.HTTP_SECONDS.labels(request.method, path).observe(seconds)
        if path not in QUIET_PATHS:
            obs.log_event(
                "request",
                logging.WARNING if status >= 500 else logging.INFO,
                method=request.method, path=request.url.path, status=status,
                duration_ms=round(seconds * 1000, 1),
            )


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


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
        doc = rag.index_document(data, Path(file.filename or "document.pdf").name)
    except rag.RagError as e:
        raise HTTPException(400, str(e))
    refresh_index_gauges()
    return doc


@app.get("/documents", response_model=list[Document])
def list_documents():
    """List every indexed document."""
    return rag.list_documents()


@app.delete("/documents/{doc_id}", status_code=204)
def delete_document(doc_id: str):
    """Remove a document from the index."""
    if not rag.delete_document(doc_id):
        raise HTTPException(404, "Document not found.")
    refresh_index_gauges()


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


# Start every endpoint's metrics at zero (see the note in observability.py).
for _route in app.routes:
    for _method in getattr(_route, "methods", None) or ():
        if _method in {"GET", "POST", "DELETE"}:
            obs.HTTP_SECONDS.labels(_method, _route.path)
            obs.HTTP_REQUESTS.labels(_method, _route.path, "200")
