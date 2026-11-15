"""
All settings in one place, read from environment variables.

Values come from (highest priority first):
  1. real environment variables (later: Docker / Kubernetes ConfigMap + Secret)
  2. the .env file in this folder (local development)
  3. the defaults written below
"""
import os

from dotenv import load_dotenv

load_dotenv()  # loads .env if present; never overrides real env variables

# ---- Secret ----
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ---- Models ----
EMBED_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")  # local embedding model
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")      # Gemini model that answers

# ---- Chunking / retrieval ----
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))        # characters per chunk
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))  # characters shared by neighbours
TOP_K = int(os.getenv("TOP_K", "4"))                    # chunks given to the LLM

# ---- Storage ----
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "documents")

# ---- Web app ----
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))  # biggest PDF accepted

if CHUNK_OVERLAP >= CHUNK_SIZE:
    raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")

