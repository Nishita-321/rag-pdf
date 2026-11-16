# The complete workflow

This is the whole project in one place: what was built, in what order, why, how the pieces connect, and how to run and fix each part.

## What the project does

You upload a PDF. You ask a question. The app finds the parts of the PDF that are about your question, hands them to Google's Gemini model, and Gemini writes an answer that mentions the page numbers.

This technique is called **RAG**: Retrieval-Augmented Generation.

- **Retrieval** = find the relevant text first.
- **Generation** = let the AI model write the answer from that text.

Why not just send the whole PDF to Gemini? Because a big PDF is slow and costly to send every time, and a model answers better from four focused paragraphs than from 300 pages.

## The journey at a glance

The project grew in six steps. Each step was one commit, and each one left a working app.

| Step | What was added | In one sentence |
|------|----------------|-----------------|
| 1 | The RAG script | A Python file that reads a PDF and answers questions in the terminal |
| 2 | Config + Gemini | Settings moved out of the code; Gemini connected as the AI model |
| 3 | Web app | A web page and an API, so it works in a browser |
| 4 | Docker | The app packed into a box that runs the same on any machine |
| 5 | Logging + Grafana | The app reports what it is doing, shown on a dashboard |
| 6 | Kubernetes | The app runs on a cluster that keeps it alive |

---

## Step 1: the RAG script

**File:** `rag.py`

This is the heart of the project. Everything added later is wrapped around it. It works in two phases:

```
Indexing (once per PDF)
  PDF -> text per page -> chunks -> embeddings -> ChromaDB (on disk)

Answering (once per question)
  question -> embedding -> 4 nearest chunks -> prompt -> Gemini -> answer
```

Together these are five actions:

| # | Action | Function | What it does |
|---|--------|----------|--------------|
| 1 | **Load** | `load_pdf` | Pulls out the text of each page. Pages with no text are skipped |
| 2 | **Chunk** | `chunk_pages` | Cuts the text into 800-character pieces that overlap by 150, so a sentence on a cut still appears whole in one piece. Each piece remembers its page |
| 3 | **Embed and store** | `index_document` | Turns each piece into numbers and saves it in ChromaDB, with the file name and page |
| 4 | **Retrieve** | `retrieve` | Turns the question into numbers and finds the 4 closest pieces |
| 5 | **Generate** | `answer` | Sends those pieces (each labelled `[file name, page N]`) and the question to Gemini, with the rule: use only this text, cite pages, say "I don't know" if it is not there |

Two ideas need explaining.

**Embedding.** A small model (`all-MiniLM-L6-v2`) turns any text into 384 numbers. Texts with a similar meaning get similar numbers. So "What does it cost?" lands close to a paragraph about pricing, even though they share no words. This model runs on your own machine and is free. It is downloaded once (about 90 MB) and loaded at startup, which is why the app takes a few seconds to start.

**Vector database.** ChromaDB stores those lists of numbers and finds the closest ones quickly. It saves everything in a folder on disk.

The libraries:

| Library | Job | Runs where |
|---------|-----|-----------|
| `pypdf` | Extracts text from PDF pages | Local |
| `sentence-transformers` | Makes the embeddings | Local, CPU is fine |
| `chromadb` | Stores and searches embeddings | Local, in `./chroma_db/` |
| `google-genai` | Calls Gemini | Google's servers |

Problems the user can fix (unreadable PDF, no text, missing key, nothing indexed) raise a `RagError`. The terminal script prints it; the web app returns it as a `400`.

Run it in the terminal: `python rag.py path/to/document.pdf`. It indexes the PDF, then answers questions about it until you type `exit`.

## Step 2: config and Gemini

**Files:** `config.py`, `.env`, `.env.example`

**Settings left the code.** They moved into `config.py`, which reads them from **environment variables**: named values handed to a program from outside when it starts. On your machine they come from `.env`, which holds your API key and is never put into git. `.env.example` is the empty template that is safe to share.

A setting takes its value from, highest priority first:

1. A real environment variable, e.g. `TOP_K=8 python rag.py doc.pdf`
2. The `.env` file
3. The default in `config.py`

Because the app reads its settings this way, Docker and Kubernetes later needed no code changes: they just set environment variables.

| Setting | Default | Meaning |
|---------|---------|---------|
| `GEMINI_API_KEY` | none, **required** | Your Gemini key, from https://aistudio.google.com/apikey |
| `LLM_MODEL` | `gemini-3.5-flash` | Gemini model that writes the answer |
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | Local embedding model |
| `CHUNK_SIZE` | `800` | Characters per chunk |
| `CHUNK_OVERLAP` | `150` | Characters shared by neighbouring chunks; must be less than `CHUNK_SIZE` |
| `TOP_K` | `4` | Chunks sent to Gemini per question |
| `CHROMA_PATH` | `./chroma_db` | Where the database is stored |
| `COLLECTION_NAME` | `documents` | ChromaDB collection name |
| `MAX_UPLOAD_MB` | `20` | Largest PDF the web app accepts |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |
| `LOG_QUESTIONS` | `false` | Put the question text in the logs |

If you change `EMBED_MODEL`, `CHUNK_SIZE` or `CHUNK_OVERLAP`, delete `chroma_db/` and upload your PDFs again. Vectors from different models cannot be compared, and old chunks keep their old size.

**Gemini writes the answers.** It replaced a local Ollama model. There is nothing to install, only an API key. The trade-off: Gemini needs internet, has a free tier with rate limits, and the question plus the 4 retrieved pieces are sent to Google. Keep that in mind for confidential PDFs. Loading, chunking, embedding and searching still all happen locally.

## Step 3: the web app

**Files:** `app.py`, `static/index.html`

This step put the app in a browser.

**`app.py`** is a web server built with FastAPI. It does no RAG work itself: it receives a request, calls the right function in `rag.py`, and sends the result back. **`static/index.html`** is the page: an upload button, a list of documents, and a chat box.

| Method | Path | Does |
|--------|------|------|
| `GET` | `/` | The web page |
| `GET` | `/health` | `{"status": "ok", ...}` if the app is working |
| `GET` | `/metrics` | Numbers for Prometheus (Step 5) |
| `POST` | `/documents` | Upload a PDF (form field `file`); calls `rag.index_document` |
| `GET` | `/documents` | List documents; calls `rag.list_documents` |
| `DELETE` | `/documents/{doc_id}` | Remove a document; calls `rag.delete_document` |
| `POST` | `/ask` | `{"question": "...", "doc_id": "..."}` returns the answer and its source pieces. Leave out `doc_id` to search all documents |

Interactive API docs are at http://localhost:8000/docs. Errors come back as `{"detail": "message"}`:

| Status | When |
|--------|------|
| `400` | Not a PDF, no text in it, nothing indexed, Gemini key missing |
| `404` | Deleting a document that does not exist |
| `413` | PDF larger than `MAX_UPLOAD_MB` |
| `422` | Malformed request, e.g. empty question |
| `502` | Gemini failed (bad key, rate limit, wrong model name) |

Holding many PDFs at once needed three changes in `rag.py`:

- Each document gets an **id** from a hash of its contents, like a fingerprint. The same file always gets the same id, so uploading it twice stores it once.
- A question can be limited to **one document**. Before this, an answer could quote the wrong PDF.
- Uploading a file again **replaces** its old chunks.

Other design choices:

- The uploaded PDF itself is not kept, only its chunks and embeddings.
- Routes are plain `def`, so FastAPI runs them in a thread pool and one slow request does not freeze the others.
- The page inserts text with `textContent`, never as HTML, so text inside a PDF cannot inject markup.

## Step 4: Docker

**Files:** `Dockerfile`, `docker-compose.yml`, `.dockerignore`

The problem: the app only worked on a machine set up just right. On your Mac, Python 3.15 was too new for ChromaDB and the install broke. Docker packs the app together with everything it needs.

| Term | Meaning |
|------|---------|
| **Image** | The packed box: Python 3.12, all packages, the embedding model, your code |
| **Container** | An image that is running |
| **Volume** | Storage outside the container, so data survives when the container is replaced |

- **`Dockerfile`** is the recipe. It uses Python 3.12 (so the 3.15 problem cannot happen), installs the CPU-only PyTorch (several GB smaller), bakes the embedding model in, runs as a normal user rather than root, and checks `/health` every 30 seconds.
- **`docker-compose.yml`** says how to run it: port 8000, settings from `.env`, and the database on a volume at `/data`.
- **`.dockerignore`** keeps `.env`, `.venv`, `chroma_db` and `pdfs` out of the image. Your API key is read when the container starts and is never baked in.

| Command | Does |
|---------|------|
| `docker compose up -d --build` | Build and start (first build takes several minutes) |
| `docker compose up -d` | Start, or apply a changed `.env` |
| `docker compose logs -f` | Follow the logs |
| `docker compose ps` | Status; `(healthy)` means `/health` answers |
| `docker compose down` | Stop. Documents are kept |
| `docker compose down -v` | Stop and **delete** all documents |
| `PORT=9000 docker compose up -d` | Use port 9000 instead of 8000 |

The image is about 2.7 GB, mostly PyTorch. To run it on a typical Intel/AMD server from an Apple Silicon Mac, build with `docker build --platform linux/amd64 -t yourname/rag-pdf:1.0 .` and push it to a registry.

## Step 5: logging and Grafana

**Files:** `observability.py`, the `monitoring/` folder

The problem: inside a container, you cannot see what the app is doing. Is it slow? Failing? How many Gemini tokens is it using? The app now reports on itself in two ways.

| | What it is | Question it answers |
|---|------------|---------------------|
| **Logs** | One JSON line per event | "What exactly happened in this request?" |
| **Metrics** | Running numbers and timings | "How is the app doing overall?" |

`observability.py` defines both. `app.py` times and logs every request. `rag.py` times each pipeline action and counts Gemini tokens. Four helper programs collect and show this, each in its own container:

```
app ── /metrics ──────────────> Prometheus ──┐
app ── stdout (JSON logs) ──> Alloy ──> Loki ├──> Grafana
```

| Program | Job |
|---------|-----|
| **Prometheus** | Reads `/metrics` every 15 seconds and keeps 15 days of history |
| **Alloy** | Picks up the app's log lines and passes them to Loki |
| **Loki** | Stores the logs and makes them searchable |
| **Grafana** | The screen you look at: graphs from Prometheus, logs from Loki |

Start it with `docker compose --profile monitoring up -d --build`, and stop it with `docker compose --profile monitoring down` (without the profile flag, the monitoring keeps running). Monitoring is optional; plain `docker compose up -d` starts only the app.

**Logs.** The main events are `document_indexed`, `question_answered` (with timings and token counts), `gemini_error` and `request`. Each request gets a short id, written on all its log lines and returned in the `X-Request-ID` header. The question text is not logged unless `LOG_QUESTIONS=true`, and API keys never are. To search logs, open Grafana → **Explore** → **Loki**:

| Query | Finds |
|-------|-------|
| `{service="app"}` | All app logs |
| `{service="app"} \| json \| level="ERROR"` | Errors |
| `{service="app"} \| json \| request_id="d7d4f3334fcf"` | Everything from one request |

**Metrics** include requests and their duration, time per pipeline action (`load`, `chunk`, `embed`, `store`, `retrieve`, `generate`), Gemini tokens, Gemini errors by code, and how many documents and chunks are stored.

**The dashboard** opens on **RAG PDF**. Reading it:

- A slow question is almost always the `generate` step (the Gemini call). `retrieve` takes milliseconds.
- A slow upload is the `embed` step, and grows with the PDF's size.
- Gemini error `429` is the rate limit, `400`/`403` a bad key, `404` a wrong model name.
- Panels stay empty until the app has had some requests and a minute has passed.

Edits made in the Grafana screen are lost on restart. To keep one, export the dashboard JSON over `monitoring/grafana/dashboards/rag-pdf.json`.

## Step 6: Kubernetes

**Files:** the `k8s/` folder, `monitoring/k8s/`

Docker runs a container on one machine. Kubernetes manages containers across a cluster and keeps them healthy: if the app crashes, it is started again automatically. You describe what you want in YAML files, and Kubernetes makes it so.

| Object | What it is | Same idea in Docker Compose |
|--------|------------|-----------------------------|
| **Namespace** `rag-pdf` | A folder that groups everything for this project | The project name |
| **Deployment** | "Keep one copy of this container running" | A service |
| **Service** | A fixed name and address for reaching the app | The service name |
| **ConfigMap** | The ordinary settings, from `k8s/config.env` | `.env` |
| **Secret** | The API key, from `k8s/secret.env` (not in git) | `.env` |
| **PersistentVolumeClaim** | A 1 GB disk for the database | A volume |
| **Probes** | Checks of `/health` at startup and while running | `HEALTHCHECK` |

`kustomization.yaml` ties the files together, so one command `kubectl apply -k k8s/` deploys everything. When a setting changes, the generated ConfigMap gets a new name and the app restarts by itself to pick it up.

Only **one copy** of the app runs, and an update stops the old one before starting the new one, because the database lives on the app's own disk and two copies cannot share it.

Deploy on Docker Desktop (first enable Kubernetes in its settings; `kubectl get nodes` should show `Ready`):

```bash
docker build -t rag-pdf:1.0 .                              # build the image
grep '^GEMINI_API_KEY=' .env > k8s/secret.env              # hand over the key
kubectl apply -k k8s/                                      # the app
kubectl apply -k monitoring/                               # monitoring (optional)
kubectl -n rag-pdf get pods                                # wait for Running

kubectl -n rag-pdf port-forward svc/app 8000:8000          # open the app
kubectl -n rag-pdf port-forward svc/grafana 3000:3000      # open Grafana (separate terminal)
```

The monitoring reuses the same Prometheus config and Grafana dashboard as Docker, because the Kubernetes Services have the same names (`app`, `loki`, `prometheus`).

| To change | Do |
|-----------|----|
| A setting | Edit `k8s/config.env`, then `kubectl apply -k k8s/` |
| The API key | Edit `k8s/secret.env`, then `kubectl apply -k k8s/` |
| The code | `docker build -t rag-pdf:1.1 .`, set `newTag: "1.1"` in `k8s/kustomization.yaml`, then `kubectl apply -k k8s/`. Always use a new tag |
| See the logs | `kubectl -n rag-pdf logs -f deploy/app` |
| See why a pod won't start | `kubectl -n rag-pdf describe pod -l app=app` |
| Remove everything | `kubectl delete -k monitoring/` then `kubectl delete -k k8s/` (**deletes all documents**) |

---

## How everything fits together

### The files and who talks to whom

```
                 static/index.html     (the page in your browser)
                        │
                        ▼
                     app.py            (web server: receives requests)
                    ╱       ╲
                   ▼         ▼
               rag.py     observability.py   (logs and metrics)
              ╱   │   ╲
             ▼    ▼    ▼
       ChromaDB  embedding  Gemini
       (on disk)  model     (Google)

   config.py  ──►  read by app.py, rag.py and observability.py
```

Each file has one job and knows little about the others. That is why each step could be added without rewriting the earlier ones.

### What happens when you upload a PDF

1. You pick a file on the page. The browser sends it to `app.py`.
2. `app.py` checks that it really is a PDF and is not too large.
3. `rag.py` extracts the text, cuts it into pieces, and turns each piece into numbers.
4. `rag.py` saves the pieces and their numbers in ChromaDB.
5. `observability.py` writes a log line and records how long each part took.
6. The page shows the document in the list.

### What happens when you ask a question

1. You type a question. The browser sends it to `app.py`, which hands it to `rag.py`.
2. `rag.py` turns the question into numbers.
3. ChromaDB returns the 4 stored pieces closest in meaning.
4. `rag.py` sends those pieces and the question to Gemini.
5. Gemini sends back the answer. This is almost all of the waiting time; everything else takes milliseconds.
6. `observability.py` logs it, with how long Gemini took and how many tokens it used.
7. The page shows the answer, with the source pieces underneath.

### How the layers stack

```
┌─ Kubernetes ─────────────────────────────────────┐
│  ┌─ Docker image ─────────────────────────────┐  │
│  │  ┌─ Web app (app.py + index.html) ──────┐  │  │
│  │  │  ┌─ RAG pipeline (rag.py) ────────┐  │  │  │
│  │  │  │  embeddings, ChromaDB, Gemini  │  │  │  │
│  │  │  └────────────────────────────────┘  │  │  │
│  │  └──────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
   Monitoring (Prometheus, Loki, Grafana) watches from the side
```

## How to run it

The same code runs three ways. Only the source of the settings changes. First get a Gemini key and put it in `.env`:

```bash
cp .env.example .env        # then set GEMINI_API_KEY=your-key-here
```

| Way | Start with | Settings and key come from |
|-----|------------|----------------------------|
| Python | `uvicorn app:app --reload` | `.env` |
| Docker | `docker compose up -d --build` | `.env`, passed in by `docker-compose.yml` |
| Kubernetes | `kubectl apply -k k8s/` (see Step 6) | `k8s/config.env` (ConfigMap) and `k8s/secret.env` (Secret) |

Docker is the easiest on a new machine. For Python, set it up first:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt     # large: PyTorch comes along, allow a few minutes
```

On **Python 3.15 only**, pip installs an old ChromaDB that crashes with `PydanticImportError`. Python 3.12 avoids this. If you must use 3.15, install ChromaDB without `onnxruntime` (this project never uses it):

```bash
pip install --no-deps "chromadb==1.5.9"
pip install build pydantic pydantic-settings pybase64 "uvicorn[standard]" numpy \
  typing-extensions opentelemetry-api opentelemetry-exporter-otlp-proto-grpc \
  opentelemetry-sdk tokenizers pypika tqdm overrides importlib-resources grpcio \
  bcrypt typer kubernetes tenacity pyyaml mmh3 orjson httpx rich jsonschema
```

| What | Address |
|------|---------|
| The app | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Grafana | http://localhost:3000 (login `admin` / `admin`) |
| Prometheus | http://localhost:9090 (Docker only) |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `GEMINI_API_KEY is not set`, or the page says the key is missing | Put the key in `.env` (or `k8s/secret.env`), then restart |
| `API key not valid`, or Gemini error `400`/`403` | Create a new key |
| `404 ... model not found` | Set `LLM_MODEL` to a current Gemini model |
| `429` / quota exceeded | Free-tier rate limit: wait a minute, or enable billing |
| `No text found. Is this a scanned PDF?` | The PDF is only images; use a text PDF |
| Answers quote the wrong document | Click the document you want in the list instead of "All documents" |
| `PydanticImportError: BaseSettings has been moved` | Python 3.15; see "How to run it" |
| `Address already in use` / `port is already allocated` | Use another port: `--port 8001` (Python) or `PORT=9000` (Docker) |
| `Cannot connect to the Docker daemon` | Start Docker Desktop |
| Code change not showing in Docker | `docker compose up -d --build` |
| Grafana panels say "No data" | Use the app, wait a minute, refresh. If only metrics are empty, check http://localhost:9090/targets |
| Pod `ErrImagePull` | Build the image: `docker build -t rag-pdf:1.0 .` |
| Pod `CrashLoopBackOff` | `kubectl -n rag-pdf logs deploy/app` |
| Pod `Running` but `0/1` ready | Still loading the model; wait up to a minute |
| `unable to find file secret.env` | `grep '^GEMINI_API_KEY=' .env > k8s/secret.env` |
| Browser cannot connect on Kubernetes | Start `port-forward` again |

## Limits and what could come next

| Limit | Effect |
|-------|--------|
| No login | Anyone who can reach the app can upload, ask and delete. Keep it on your own machine or a private network |
| No OCR | Scanned PDFs (pictures of pages) have no text to read |
| One copy of the app only | The database lives on the app's own disk, so the app cannot be scaled out |
| No conversation memory | Each question is answered alone; "what about the second one?" will not work |
| Chunks cut by character count | Words and sentences can be split mid-way |
| No relevance cutoff | An off-topic question still gets 4 pieces, however poor the match |
| Large uploads are slow | The whole PDF is embedded inside the upload request, even if nothing changed |
| No streaming | The answer appears all at once |
| Grafana password is `admin` and there are no alerts | Fine locally; change it anywhere else |
| Logs are kept forever | Loki's storage slowly grows |

Possible next steps: split on sentence boundaries, drop poorly matching pieces, send earlier questions so follow-ups work, skip re-embedding an unchanged file, run ChromaDB as its own server so the app can scale, add HTTPS and a login for a public cluster, add OCR, and stream answers as they are written.

## Words used in this project

| Word | Meaning |
|------|---------|
| **RAG** | Find the relevant text first, then let an AI model answer from it |
| **Chunk** | A small piece of a document's text |
| **Embedding** | A list of numbers that stands for the meaning of a text |
| **Vector database** | A database that finds the stored embeddings closest to a given one |
| **LLM** | Large language model: the AI that writes the answer (here, Gemini) |
| **Token** | The unit an LLM counts text in, roughly three-quarters of a word. Gemini bills by tokens |
| **API** | A way for one program to ask another to do something |
| **Environment variable** | A named value given to a program from outside when it starts |
| **Image / container** | A packed app / that app running |
| **Volume** | Storage that outlives a container |
| **Log** | A written record of one event |
| **Metric** | A number measured over time |
| **Pod** | Kubernetes' name for a running container |
| **Manifest** | A YAML file describing something Kubernetes should create |
