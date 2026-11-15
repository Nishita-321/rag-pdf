# Setup and run

## 1. Python environment

```bash
cd rag-pdf
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The install is large (PyTorch comes with `sentence-transformers`). Allow a few minutes.

### Python 3.15 only: extra step for ChromaDB

ChromaDB depends on `onnxruntime`, which has no build for Python 3.15 yet. On 3.15, pip silently falls back to a very old ChromaDB (0.3.x) that crashes on import with:

```
PydanticImportError: `BaseSettings` has been moved to the `pydantic-settings` package
```

This project never uses `onnxruntime` (it is only for ChromaDB's built-in embedder; we use `sentence-transformers`), so install ChromaDB without it:

```bash
pip install --no-deps "chromadb==1.5.9"
pip install build pydantic pydantic-settings pybase64 "uvicorn[standard]" numpy \
  typing-extensions opentelemetry-api opentelemetry-exporter-otlp-proto-grpc \
  opentelemetry-sdk tokenizers pypika tqdm overrides importlib-resources grpcio \
  bcrypt typer kubernetes tenacity pyyaml mmh3 orjson httpx rich jsonschema
```

pip will warn that `onnxruntime` is missing. That warning is expected. On Python 3.13 or older, none of this is needed.

## 2. Gemini API key

1. Create a key at https://aistudio.google.com/apikey
2. Create your `.env` file and paste the key in:

```bash
cp .env.example .env
```

```
GEMINI_API_KEY=your-key-here
```

`.env` is in `.gitignore`. Never commit it.

## 3. Run the web app

```bash
uvicorn app:app --reload
```

Open http://localhost:8000. Details in [05-web-app.md](05-web-app.md).

## 4. Or run in the terminal

```bash
python rag.py path/to/document.pdf
```

Expected output:

```
Indexed 42 chunks from 12 pages.

Ask a question (or 'exit'):
```

To change a setting for one run without editing `.env`:

```bash
TOP_K=8 python rag.py path/to/document.pdf
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Usage: python rag.py path/to/document.pdf` | No PDF path given | `python rag.py pdfs/test.pdf` |
| `PydanticImportError: BaseSettings has been moved` | Old ChromaDB installed on Python 3.15 | See "Python 3.15 only" above |
| `Address already in use` | Port 8000 is taken | `uvicorn app:app --reload --port 8001` |
| `GEMINI_API_KEY is not set` | No `.env`, or key left empty | Do step 2 |
| `API key not valid` (400) | Wrong or revoked key | Create a new key |
| `404 ... model not found` | `LLM_MODEL` name is wrong or retired | Set `LLM_MODEL` in `.env` to a current Gemini model |
| `429` / quota exceeded | Free-tier rate limit | Wait a minute, or enable billing |
| `No text found. Is this a scanned PDF?` | PDF is images only | Use a text PDF, or add OCR |
| Answers quote the wrong document | "All documents" is selected | Click the document you want in the list |
| Slow first start | Embedding model downloading | One time only |
