# How the pipeline in `rag.py` works

`rag.py` is a complete RAG (Retrieval-Augmented Generation) pipeline. It is used by the terminal script and by the web app.

RAG means: instead of hoping the LLM already knows the answer, you find the relevant parts of your document first and paste them into the prompt.

## The two phases

```
Indexing (once per PDF)
  PDF -> text per page -> chunks -> embeddings -> ChromaDB (on disk)

Answering (once per question)
  question -> embedding -> 4 nearest chunks -> prompt -> Gemini -> answer
```

## The tools

| Library | Job | Runs where |
|---------|-----|-----------|
| `pypdf` | Extracts text from PDF pages | Local |
| `sentence-transformers` | Turns text into a vector (384 numbers for `all-MiniLM-L6-v2`) | Local, CPU is fine |
| `chromadb` | Stores vectors and finds the nearest ones | Local, in `./chroma_db/` |
| `google-genai` | Calls the Gemini LLM that writes the answer | Google's servers |

Loading, chunking, embedding and search all run on your machine. Only the final prompt (retrieved chunks plus your question) is sent to Gemini.

## The code, section by section

### Settings

Defined in `config.py` and read from environment variables. Full list in [04-config-and-gemini.md](04-config-and-gemini.md).

### Startup

Loads the embedding model, opens the database and creates the Gemini client. This runs at import time, so the first run downloads the model (about 90 MB) and every start takes a few seconds.

### 1. Load: `load_pdf(data)`

Takes the PDF's bytes and returns `(page_number, text)` per page. Pages with no text are skipped. A scanned PDF has no text at all, which is what triggers the OCR error.

### 2. Chunk: `chunk_pages(pages)`

Cuts each page into 800-character pieces, moving forward 650 characters each time (800 - 150). So each chunk repeats the last 150 characters of the previous one. Each chunk remembers its page number.

Why chunk at all: an embedding of a whole page is too blurry to match a specific question, and small chunks keep the prompt short.

### 3. Index: `index_document(data, name)`

1. Computes the document id: the first 16 characters of the SHA-256 hash of the file. The same file always gets the same id.
2. Loads, chunks and embeds.
3. Deletes any chunks already stored under that id, then adds the new ones with metadata `doc_id`, `source` (the file name) and `page`.

Returns `{"doc_id", "name", "pages", "chunks"}`.

`list_documents()` and `delete_document(doc_id)` read and remove what is stored.

### 4. Retrieve: `retrieve(question, doc_id=None)`

Embeds the question with the same model and asks ChromaDB for the 4 closest chunks. With a `doc_id` it searches only that document; without one it searches all of them. "Closest" means the vectors point in a similar direction, which roughly means similar meaning.

### 5. Generate: `answer(question, doc_id=None)`

Builds a context block with a `[file name, page N]` label on each chunk, then sends it to Gemini with a system instruction that says: use only this context, cite pages, say "I don't know" if it is not there. Returns the answer and the chunks used.

### Errors

Problems the user can fix (unreadable PDF, no text, missing key, nothing indexed) raise `RagError`. The terminal script prints it; the web app returns it as a `400`.

### Main loop

`python rag.py file.pdf` indexes that PDF, then answers questions about that PDF only, until you type `exit`.

## Known limits

| # | Problem | Effect |
|---|---------|--------|
| 1 | Chunks are cut by character count | Words and sentences are split mid-way; a chunk never spans two pages |
| 2 | "Sources" lists every retrieved chunk | It shows what was retrieved, not what Gemini actually used |
| 3 | No relevance cutoff | An off-topic question still gets 4 chunks, however poor the match |
| 4 | Every upload re-embeds the whole PDF | Slow for large files, even when nothing changed |
| 5 | No conversation memory | Each question is answered on its own |
