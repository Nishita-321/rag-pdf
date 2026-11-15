# Roadmap

Each step is small, leaves the project working, and gets its own doc when built.

| Step | What | Status | Files |
|------|------|--------|-------|
| 1 | Plain script | Done | `rag.py` |
| 2 | Env config + Gemini | Done, see [04-config-and-gemini.md](04-config-and-gemini.md) | `config.py`, `.env.example` |
| 3 | Fix the Step 1 limits | Next | `rag.py` |
| 4 | Web API with FastAPI | | `app.py` |
| 5 | Simple web page | | `static/index.html` |
| 6 | Docker | | `Dockerfile` |
| 7 | Kubernetes | | `k8s/*.yaml` |

## Step 3: fix the limits

From the table in [01-current-pipeline.md](01-current-pipeline.md):

- Filter retrieval by document, so one PDF's answers never quote another.
- Use a hash of the file contents as the document id, so the path spelling does not matter and unchanged files are not re-embedded.
- Delete a document's old chunks before re-indexing it.
- Split on sentence or paragraph boundaries instead of raw character counts.
- Catch Gemini errors (bad key, rate limit, no network) and print a clear message.

## Step 4: web API

| Endpoint | Does |
|----------|------|
| `POST /documents` | Upload a PDF and index it |
| `GET /documents` | List indexed documents |
| `POST /ask` | Question in, answer and source pages out |
| `GET /health` | For Kubernetes probes later |

`rag.py` becomes a module that `app.py` imports. The terminal loop keeps working.

## Step 5: web page

One HTML file with an upload box and a chat box that calls the Step 4 API. No frontend framework.

## Step 6: Docker

One container for the app. Settings come in as environment variables, ChromaDB data goes on a volume so it survives restarts. Since Gemini is a hosted API, there is no LLM container to run.

## Step 7: Kubernetes

| Object | For |
|--------|-----|
| Deployment + Service | The app |
| ConfigMap | The non-secret settings from `config.py` |
| Secret | `GEMINI_API_KEY` |
| PersistentVolumeClaim | ChromaDB data |

One design choice appears here: the embedded on-disk ChromaDB only works with a single app replica. To scale past one, ChromaDB has to run as its own server.

## Optional later

- OCR for scanned PDFs
- Streaming answers token by token
- Reranking retrieved chunks for better accuracy
- A small evaluation set of questions with known answers, to measure whether changes help
