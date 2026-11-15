# Step 2: env config and Gemini

Two changes in this step:

1. Settings moved out of `rag.py` into `config.py`, read from environment variables.
2. The answer is now written by Google Gemini instead of a local Ollama model.

Embeddings are unchanged: still `sentence-transformers`, still local and free. Only the final "write the answer" call goes to Gemini.

## Files

| File | Purpose | In git? |
|------|---------|---------|
| `config.py` | Reads every setting from the environment, with defaults | Yes |
| `.env.example` | Template listing every setting | Yes |
| `.env` | Your real values, including the API key | **No** (in `.gitignore`) |
| `rag.py` | Imports settings from `config.py`; calls Gemini | Yes |

## How a setting gets its value

Highest priority first:

1. A real environment variable, e.g. `TOP_K=8 python rag.py doc.pdf`
2. The `.env` file
3. The default in `config.py`

This order is what makes Docker and Kubernetes easy later: the same code runs everywhere, and a ConfigMap or Secret just sets environment variables.

## Settings

| Variable | Default | Meaning |
|----------|---------|---------|
| `GEMINI_API_KEY` | none, **required** | Your Gemini key |
| `LLM_MODEL` | `gemini-2.5-flash` | Gemini model that writes the answer |
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | Local embedding model |
| `CHUNK_SIZE` | `800` | Characters per chunk |
| `CHUNK_OVERLAP` | `150` | Characters shared between neighbouring chunks; must be less than `CHUNK_SIZE` |
| `TOP_K` | `4` | Chunks sent to Gemini per question |
| `CHROMA_PATH` | `./chroma_db` | Where the vector database is stored |
| `COLLECTION_NAME` | `documents` | ChromaDB collection name |

Two settings need care:

- **`EMBED_MODEL`**: if you change it, delete `chroma_db/` and re-index. Vectors from different models cannot be compared.
- **`CHUNK_SIZE` / `CHUNK_OVERLAP`**: changing them only affects PDFs indexed afterwards. Delete `chroma_db/` for a clean re-index.

## The Gemini call

In `answer()` in `rag.py`:

```python
response = llm.models.generate_content(
    model=LLM_MODEL,
    contents=f"Context:\n{context}\n\nQuestion: {question}",
    config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
)
return response.text
```

| Part | Role |
|------|------|
| `llm` | `genai.Client(api_key=GEMINI_API_KEY)`, from the `google-genai` package |
| `system_instruction` | The rules: use only the context, cite pages, admit when unknown |
| `contents` | The retrieved chunks plus the question |
| `response.text` | The answer |

## What changed compared with Ollama

| | Ollama (before) | Gemini (now) |
|---|---|---|
| Runs | On your machine | Google's servers |
| Setup | Install Ollama, pull a 2 GB model | One API key |
| Cost | Free | Free tier with rate limits, then paid |
| Privacy | Nothing leaves your machine | Retrieved chunks and your question are sent to Google |
| Internet | Not needed | Needed |

The privacy row matters if you index confidential PDFs.
