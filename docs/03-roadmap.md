# Roadmap

Each step is small, leaves the project working, and gets its own doc when built.

| Step | What | Status | Files |
|------|------|--------|-------|
| 1 | Plain script | Done | `rag.py` |
| 2 | Env config + Gemini | Done, see [04-config-and-gemini.md](04-config-and-gemini.md) | `config.py`, `.env.example` |
| 3 | Web app: FastAPI + web page, multi-document support | Done, see [05-web-app.md](05-web-app.md) | `app.py`, `static/index.html` |
| 4 | Docker | Done, see [06-docker.md](06-docker.md) | `Dockerfile`, `docker-compose.yml` |
| 5 | Logging, metrics and Grafana | Done, see [07-monitoring.md](07-monitoring.md) | `observability.py`, `monitoring/` |
| 6 | Kubernetes | Done, see [08-kubernetes.md](08-kubernetes.md) | `k8s/`, `monitoring/k8s/` |
| 7 | Quality improvements | Optional | `rag.py` |

## Step 7: quality improvements

- Split on sentence or paragraph boundaries instead of raw character counts.
- Skip re-embedding when an identical file is uploaded again.
- Drop retrieved chunks that are a poor match.
- Send earlier questions to Gemini so follow-up questions work.

## Optional later

- Run ChromaDB as its own server, so the app can have more than one replica
- Ingress with HTTPS and a login, for running on a public cluster
- Alerts in Grafana
- OCR for scanned PDFs
- Streaming answers token by token
- Reranking retrieved chunks for better accuracy
- A small evaluation set of questions with known answers, to measure whether changes help
