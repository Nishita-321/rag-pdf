# Setup and run

## 1. Python environment

```bash
cd rag-pdf
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The install is large (PyTorch comes with `sentence-transformers`). Allow a few minutes.

## 2. Ollama

Ollama is not installed on this machine yet.

```bash
brew install ollama
ollama serve            # leave running in its own terminal
ollama pull llama3.2    # about 2 GB, one time
```

## 3. Run

```bash
python rag.py path/to/document.pdf
```

Expected output:

```
Indexed 42 chunks from 12 pages.

Ask a question (or 'exit'):
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `No text found. Is this a scanned PDF?` | PDF is images only | Use a text PDF, or add OCR |
| `ConnectionError` / connection refused | Ollama server not running | `ollama serve` |
| `model "llama3.2" not found` | Model not pulled | `ollama pull llama3.2` |
| Answers quote the wrong document | Old PDFs still in the database | Delete the `chroma_db/` folder and re-run |
| Slow first start | Embedding model downloading | One time only |
