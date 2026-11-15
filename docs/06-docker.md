# Step 4: Docker

The whole app now runs in a container. A machine needs only Docker: no Python, no virtual environment, no manual package fixes.

## Run on any machine

```bash
cp .env.example .env        # then put your key in GEMINI_API_KEY
docker compose up -d --build
```

Open http://localhost:8000.

The first build takes several minutes (it downloads PyTorch and the embedding model). Later builds are fast.

## Everyday commands

| Command | Does |
|---------|------|
| `docker compose up -d` | Start in the background |
| `docker compose up -d --build` | Rebuild after a code change, then start |
| `docker compose logs -f` | Follow the logs |
| `docker compose ps` | Show status; `(healthy)` means `/health` is answering |
| `docker compose down` | Stop. Indexed documents are kept |
| `docker compose down -v` | Stop and **delete** all indexed documents |
| `PORT=9000 docker compose up -d` | Use port 9000 instead of 8000 |

After changing `.env`, run `docker compose up -d` again to apply it.

## Files

| File | Role |
|------|------|
| `Dockerfile` | Recipe for the image: Python, packages, embedding model, code |
| `docker-compose.yml` | How to run it: port, `.env`, data volume |
| `.dockerignore` | What must not go into the image: `.env`, `.venv`, `chroma_db`, `pdfs` |
| `requirements.txt` | Now pins exact versions, so every build installs the same packages |

## The Dockerfile, step by step

| Step | What | Why |
|------|------|-----|
| `FROM python:3.12-slim` | Start from a small Python 3.12 image | Every package has a build for 3.12, so the Python 3.15 ChromaDB problem cannot happen |
| `pip install` with the PyTorch CPU index | Install packages | The default Linux PyTorch bundles GPU libraries and is several GB larger. The app only needs CPU |
| Download the embedding model | Store `all-MiniLM-L6-v2` inside the image | The container starts fast and does not fetch the model on first run |
| `COPY` the code | Add `config.py`, `rag.py`, `app.py`, `static/` | Copied after the packages, so a code change rebuilds in seconds |
| `USER appuser` | Run as a normal user | A bug in the app cannot act as root in the container |
| `HEALTHCHECK` | Call `/health` every 30 seconds | Docker can tell whether the app is working, not just running |
| `CMD uvicorn ... --host 0.0.0.0` | Start the server | `0.0.0.0` makes it reachable from outside the container |

## Configuration

Settings reach the container as environment variables, which is exactly what `config.py` reads.

| Source | Sets |
|--------|------|
| `.env` (via `env_file`) | `GEMINI_API_KEY` and everything else you put there |
| `docker-compose.yml` `environment` | `CHROMA_PATH=/data/chroma_db`. This overrides `.env`, so the database is always on the volume |

The `.env` file is read when the container starts. It is never copied into the image, so the image contains no secret and is safe to share.

## Data

Indexed documents live in a Docker volume named `rag-pdf_rag_data`, mounted at `/data`.

| Action | Data |
|--------|------|
| Restart, `down` then `up`, rebuild | Kept |
| `docker compose down -v` | Deleted |

The container's database is separate from the local `./chroma_db` folder used when you run without Docker.

## Without compose

```bash
docker build -t rag-pdf .
docker run -d -p 8000:8000 --env-file .env -v rag_data:/data rag-pdf
```

## Moving the image to another machine

Either copy the project and run `docker compose up -d --build` there, or push the image to a registry:

```bash
docker tag rag-pdf yourname/rag-pdf:1.0
docker push yourname/rag-pdf:1.0
```

An image built on an Apple Silicon Mac is `arm64`. For a typical Intel/AMD server, build for that platform:

```bash
docker build --platform linux/amd64 -t yourname/rag-pdf:1.0 .
```

## Limits

| Limit | Effect |
|-------|--------|
| Image is about 2.7 GB | Mostly PyTorch. Slow first pull |
| Needs internet at runtime | For Gemini calls |
| One container only | The on-disk ChromaDB cannot be shared by several containers |
| Changing `EMBED_MODEL` in `.env` | The new model is downloaded at start instead of coming from the image. Pass `--build-arg EMBED_MODEL=...` to bake it in |

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Cannot connect to the Docker daemon` | Docker Desktop is not running | Start Docker Desktop |
| `env file .env not found` | No `.env` yet | `cp .env.example .env` |
| `port is already allocated` | Port 8000 is in use | `PORT=9000 docker compose up -d` |
| Page says Gemini key missing | Key empty in `.env` | Fill it in, then `docker compose up -d` |
| Code change not showing | Old image still running | `docker compose up -d --build` |
