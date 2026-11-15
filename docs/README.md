# Docs

Three ways to run the app, simplest first:

| How | Command | Doc |
|-----|---------|-----|
| Python | `uvicorn app:app --reload` | [02-setup-and-run.md](02-setup-and-run.md) |
| Docker | `docker compose up -d --build` | [06-docker.md](06-docker.md) |
| Kubernetes | `kubectl apply -k k8s/` | [08-kubernetes.md](08-kubernetes.md) |

## All docs

| File | What it covers |
|------|----------------|
| [01-current-pipeline.md](01-current-pipeline.md) | How the RAG pipeline in `rag.py` works, and its known limits |
| [02-setup-and-run.md](02-setup-and-run.md) | How to install and run it on your machine |
| [03-roadmap.md](03-roadmap.md) | The steps, in order, and which are done |
| [04-config-and-gemini.md](04-config-and-gemini.md) | Step 2: settings from environment variables, and Gemini as the LLM |
| [05-web-app.md](05-web-app.md) | Step 3: the FastAPI web app, its API and design decisions |
| [06-docker.md](06-docker.md) | Step 4: running the app in Docker on any machine |
| [07-monitoring.md](07-monitoring.md) | Step 5: JSON logs, Prometheus metrics and the Grafana dashboard |
| [08-kubernetes.md](08-kubernetes.md) | Step 6: deploying the app and monitoring to Kubernetes |
