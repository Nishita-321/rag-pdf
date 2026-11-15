# RAG PDF

Upload PDFs and ask questions about them. Answers come from the documents themselves, with page citations and the source passages shown.

It is a small, complete RAG (Retrieval-Augmented Generation) application: a web page, an HTTP API, a vector database, monitoring, and deployment files for Docker and Kubernetes.

## How it works

```
Upload:  PDF -> text -> chunks -> embeddings -> ChromaDB
Ask:     question -> embedding -> 4 closest chunks -> Gemini -> answer with page numbers
```

| Part | Tool | Runs |
|------|------|------|
| PDF text extraction | `pypdf` | Locally |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`) | Locally, on CPU |
| Vector database | ChromaDB | Locally, on disk |
| Answer generation | Google Gemini | Google's API |
| Web server | FastAPI | Locally |
| Monitoring | Prometheus, Loki, Grafana | Locally, optional |

Only the question and the retrieved passages are sent to Gemini. The PDFs themselves stay on your machine.

## Before you start

You need a Gemini API key. Create one at https://aistudio.google.com/apikey, then:

```bash
cp .env.example .env
```

Open `.env` and set `GEMINI_API_KEY=your-key`.

## Ways to run it

| Method | Best for | Needs |
|--------|----------|-------|
| [Docker](#1-docker) | Just using it, on any machine | Docker |
| [Docker with monitoring](#2-docker-with-monitoring) | Seeing logs and metrics in Grafana | Docker |
| [Kubernetes](#3-kubernetes) | Running on a cluster | Docker and a cluster |
| [Python](#4-python) | Changing the code | Python 3.12 |
| [Terminal only](#5-terminal-only) | A quick chat with one PDF, no browser | Python 3.12 |

### 1. Docker

```bash
docker compose up -d --build
```

Open http://localhost:8000. Stop with `docker compose down`.

The first build takes several minutes. Details: [docs/06-docker.md](docs/06-docker.md)

### 2. Docker with monitoring

```bash
docker compose --profile monitoring up -d --build
```

Open the app at http://localhost:8000 and Grafana at http://localhost:3000 (login `admin` / `admin`).

Stop with `docker compose --profile monitoring down`. Details: [docs/07-monitoring.md](docs/07-monitoring.md)

### 3. Kubernetes

```bash
docker build -t rag-pdf:1.0 .
grep '^GEMINI_API_KEY=' .env > k8s/secret.env
kubectl apply -k k8s/            # the app
kubectl apply -k monitoring/     # monitoring, optional
```

Nothing is reachable on `localhost` until you forward a port. Run each in its own terminal:

```bash
kubectl -n rag-pdf port-forward svc/app 8000:8000
kubectl -n rag-pdf port-forward svc/grafana 3000:3000
```

Remove with `kubectl delete -k monitoring/` and `kubectl delete -k k8s/`. Details: [docs/08-kubernetes.md](docs/08-kubernetes.md)

### 4. Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Open http://localhost:8000. Stop with Ctrl+C.

Python 3.12 is the tested version (it is what the Docker image uses). On Python 3.15 the ChromaDB install needs an extra step. Details: [docs/02-setup-and-run.md](docs/02-setup-and-run.md)

### 5. Terminal only

After the Python setup above:

```bash
python rag.py path/to/document.pdf
```

Type questions at the prompt; `exit` to quit. This uses no port.

## Ports

Everything is served on `localhost`.

| Port | What | URL | Available in |
|------|------|-----|--------------|
| 8000 | The app | http://localhost:8000 | Docker, Kubernetes, Python |
| 3000 | Grafana | http://localhost:3000 | Docker with monitoring, Kubernetes |
| 9090 | Prometheus | http://localhost:9090 | Docker with monitoring |

On port 8000:

| Path | What |
|------|------|
| `/` | The web page |
| `/docs` | Interactive API documentation |
| `/health` | Status check |
| `/metrics` | Prometheus metrics |

Loki (logs) and Alloy (log shipping) run without a `localhost` port. Grafana reaches them internally.

### If a port is already in use

| Method | Change the port with |
|--------|----------------------|
| Docker, app | `PORT=9000 docker compose up -d` |
| Docker, Grafana | `GRAFANA_PORT=3001 docker compose --profile monitoring up -d` |
| Kubernetes | Change the first number: `port-forward svc/app 9000:8000` |
| Python | `uvicorn app:app --reload --port 9000` |

Prometheus's port 9090 is fixed in `docker-compose.yml`.

Docker and Python both use port 8000 by default, so they cannot run at the same time without changing one.

### Kubernetes: reaching Prometheus

Not forwarded by default. To open it:

```bash
kubectl -n rag-pdf port-forward svc/prometheus 9090:9090
```

## Where your data lives

Each method keeps its own separate set of indexed documents.

| Method | Stored in | Deleted by |
|--------|-----------|------------|
| Python, terminal | `./chroma_db/` folder | Deleting the folder |
| Docker | Volume `rag-pdf_rag_data` | `docker compose down -v` |
| Kubernetes | PersistentVolumeClaim `app-data` | `kubectl delete -k k8s/` |

## Settings

All settings are environment variables with defaults, set in `.env` (Docker, Python) or `k8s/config.env` (Kubernetes). Only `GEMINI_API_KEY` is required. Full list: [docs/04-config-and-gemini.md](docs/04-config-and-gemini.md)

## Project layout

| Path | What |
|------|------|
| `rag.py` | The RAG pipeline: load, chunk, embed, store, retrieve, answer |
| `app.py` | FastAPI web server |
| `config.py` | Settings from environment variables |
| `observability.py` | JSON logging and Prometheus metrics |
| `static/index.html` | The web page |
| `Dockerfile`, `docker-compose.yml` | Docker image and services |
| `k8s/` | Kubernetes manifests for the app |
| `monitoring/` | Prometheus, Loki, Alloy and Grafana config, for Docker and Kubernetes |
| `docs/` | Step-by-step documentation |

## Documentation

| Doc | Covers |
|-----|--------|
| [01-current-pipeline.md](docs/01-current-pipeline.md) | How the RAG pipeline works |
| [02-setup-and-run.md](docs/02-setup-and-run.md) | Python setup and troubleshooting |
| [03-roadmap.md](docs/03-roadmap.md) | What was built, in order, and what could come next |
| [04-config-and-gemini.md](docs/04-config-and-gemini.md) | Settings and the Gemini call |
| [05-web-app.md](docs/05-web-app.md) | The web app and its API |
| [06-docker.md](docs/06-docker.md) | Docker |
| [07-monitoring.md](docs/07-monitoring.md) | Logs, metrics and the Grafana dashboard |
| [08-kubernetes.md](docs/08-kubernetes.md) | Kubernetes |

## Limits

- **No login.** Anyone who can reach the app can upload, ask and delete. Keep it on `localhost` or a private network.
- **Text PDFs only.** Scanned PDFs need OCR, which is not included.
- **One instance.** The vector database is on local disk, so the app cannot be scaled to several copies.
- **No conversation memory.** Each question is answered on its own; follow-up questions do not see earlier ones.
