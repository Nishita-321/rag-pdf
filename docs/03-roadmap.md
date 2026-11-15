# Roadmap

Each step is small, leaves the project working, and gets its own doc when built.

| Step | What | Status | Files |
|------|------|--------|-------|
| 1 | Plain script | Done | `rag.py` |
| 2 | Env config + Gemini | Done, see [04-config-and-gemini.md](04-config-and-gemini.md) | `config.py`, `.env.example` |
| 3 | Web app: FastAPI + web page, multi-document support | Done, see [05-web-app.md](05-web-app.md) | `app.py`, `static/index.html` |
| 4 | Docker | Next | `Dockerfile` |
| 5 | Kubernetes | | `k8s/*.yaml` |
| 6 | Quality improvements | | `rag.py` |

## Step 4: Docker

One container for the app. Settings come in as environment variables, ChromaDB data goes on a volume so it survives restarts. Since Gemini is a hosted API, there is no LLM container to run.

## Step 5: Kubernetes

| Object | For |
|--------|-----|
| Deployment + Service | The app |
| ConfigMap | The non-secret settings from `config.py` |
| Secret | `GEMINI_API_KEY` |
| PersistentVolumeClaim | ChromaDB data |

One design choice appears here: the embedded on-disk ChromaDB only works with a single app replica. To scale past one, ChromaDB has to run as its own server.

## Step 6: quality improvements

- Split on sentence or paragraph boundaries instead of raw character counts.
- Skip re-embedding when an identical file is uploaded again.
- Drop retrieved chunks that are a poor match.
- Send earlier questions to Gemini so follow-up questions work.

## Optional later

- OCR for scanned PDFs
- Streaming answers token by token
- Reranking retrieved chunks for better accuracy
- A small evaluation set of questions with known answers, to measure whether changes help
