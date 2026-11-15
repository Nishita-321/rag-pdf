# Step 1: what `rag.py` does today

`rag.py` is a complete RAG (Retrieval-Augmented Generation) pipeline in one script. You give it a PDF, it indexes it, then you ask questions in the terminal.

RAG means: instead of hoping the LLM already knows the answer, you find the relevant parts of your document first and paste them into the prompt.

## The two phases

```
Indexing (once per PDF)
  PDF -> text per page -> chunks -> embeddings -> ChromaDB (on disk)

Answering (once per question)
  question -> embedding -> 4 nearest chunks -> prompt -> Ollama LLM -> answer
```

## The tools

| Library | Job | Runs where |
|---------|-----|-----------|
| `pypdf` | Extracts text from PDF pages | Local |
| `sentence-transformers` | Turns text into a vector (384 numbers for `all-MiniLM-L6-v2`) | Local, CPU is fine |
| `chromadb` | Stores vectors and finds the nearest ones | Local, in `./chroma_db/` |
| `ollama` | Runs the LLM (`llama3.2`) | Local Ollama server |

Nothing leaves your machine, and nothing costs money.

## The code, section by section

### Settings (lines 17-22)

| Setting | Value | Meaning |
|---------|-------|---------|
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | Embedding model |
| `LLM_MODEL` | `llama3.2` | Model that writes the answer |
| `CHUNK_SIZE` | 800 | Characters per chunk |
| `CHUNK_OVERLAP` | 150 | Characters shared between neighbouring chunks |
| `TOP_K` | 4 | Chunks sent to the LLM per question |

### Startup (lines 24-26)

Loads the embedding model and opens the database. This runs at import time, so the first run downloads the model (about 90 MB) and every run takes a few seconds to start.

### 1. Load: `load_pdf` (lines 30-38)

Reads each page and returns `(page_number, text)`. Pages with no text are skipped. A scanned PDF has no text at all, which is why `index_document` exits with the OCR message.

### 2. Chunk: `chunk_pages` (lines 42-51)

Cuts each page into 800-character pieces, moving forward 650 characters each time (800 - 150). So each chunk repeats the last 150 characters of the previous one. Each chunk remembers its page number.

Why chunk at all: an embedding of a whole page is too blurry to match a specific question, and small chunks keep the prompt short.

### 3. Index: `index_document` (lines 55-71)

Embeds every chunk and writes text, vector and metadata (`source`, `page`) to ChromaDB. It uses `upsert` with ids like `myfile.pdf-0`, so running the same file again overwrites instead of duplicating.

### 4. Retrieve: `retrieve` (lines 75-78)

Embeds the question with the same model and asks ChromaDB for the 4 closest chunks. "Closest" means the vectors point in a similar direction, which roughly means similar meaning.

### 5. Generate: `answer` (lines 82-105)

Builds a context block with a `[Page N]` label on each chunk, then sends it to the LLM with a system prompt that says: use only this context, cite pages, say "I don't know" if it is not there. Returns the answer and the chunks used.

### Main loop (lines 109-123)

Indexes the PDF from the command line, then loops on questions until you type `exit`.

## Known limits

These are the things worth fixing as the project grows, most important first.

| # | Problem | Effect |
|---|---------|--------|
| 1 | Retrieval searches **every document ever indexed**, not only the one you passed in | Index `a.pdf` yesterday and `b.pdf` today, and answers about `b.pdf` can quote `a.pdf` |
| 2 | Chunk ids use the path exactly as typed | `doc.pdf` and `./doc.pdf` are stored as two documents |
| 3 | Re-indexing a PDF that got shorter leaves old chunks behind | Stale text can still be retrieved |
| 4 | Chunks are cut by character count | Words and sentences are split mid-way; a chunk never spans two pages |
| 5 | No error handling around Ollama | If Ollama is not running or the model is not pulled, the script crashes with a stack trace |
| 6 | "Sources" lists every retrieved page | It shows what was retrieved, not what the LLM actually used |
| 7 | No relevance cutoff | An off-topic question still gets 4 chunks, however poor the match |
| 8 | Every run re-embeds the whole PDF | Slow for large files, even when nothing changed |
