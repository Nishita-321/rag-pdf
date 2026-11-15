# Roadmap

Proposed order. Each step is small, leaves the project working, and gets its own doc when built. The direction (web app, then config, then Kubernetes) comes from the comments already in `rag.py`.

| Step | What | Why | New files |
|------|------|-----|-----------|
| 1 | Plain script | Done | `rag.py` |
| 2 | Fix the Step 1 limits | Correct answers before adding features | `rag.py` |
| 3 | Config from environment variables | Needed for Docker and Kubernetes | `config.py` |
| 4 | Web API with FastAPI | Upload and ask over HTTP instead of the terminal | `app.py` |
| 5 | Simple web page | Use it from a browser | `static/index.html` |
| 6 | Docker | Same environment everywhere | `Dockerfile`, `docker-compose.yml` |
| 7 | Kubernetes | Deploy, scale, configure with a ConfigMap | `k8s/*.yaml` |

## Step 2: fix the limits

From the table in [01-current-pipeline.md](01-current-pipeline.md):

- Filter retrieval by document, so one PDF's answers never quote another.
- Use a hash of the file contents as the document id, so the path spelling does not matter and unchanged files are not re-embedded.
- Delete a document's old chunks before re-indexing it.
- Split on sentence or paragraph boundaries instead of raw character counts.
- Catch Ollama errors and print a clear message.

## Step 3: config

Move the five settings, the database path and the Ollama URL into `config.py`, read from environment variables with today's values as defaults. Nothing changes in behaviour; the values just become changeable without editing code.

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

Two containers with `docker-compose`: the app and Ollama. ChromaDB data and Ollama models go on volumes so they survive restarts.

## Step 7: Kubernetes

| Object | For |
|--------|-----|
| Deployment + Service | The app |
| Deployment + Service + PersistentVolumeClaim | Ollama and its models |
| ConfigMap | The Step 3 settings |
| PersistentVolumeClaim | ChromaDB data |

One design choice appears here: the embedded on-disk ChromaDB only works with a single app replica. To scale past one, ChromaDB has to run as its own server.

## Optional later

- OCR for scanned PDFs
- Streaming answers token by token
- Reranking retrieved chunks for better accuracy
- A small evaluation set of questions with known answers, to measure whether changes help
