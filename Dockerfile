# Python 3.12: every dependency has a ready-made build for it.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf \
    CHROMA_PATH=/data/chroma_db

WORKDIR /app

# 1. Dependencies first, so this slow layer is cached until requirements.txt changes.
#    The extra index gives the CPU-only PyTorch build (the default Linux build
#    bundles GPU libraries and is several GB larger).
COPY requirements.txt .
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# 2. Download the embedding model into the image, so the container starts fast
#    and does not need to fetch it on first run.
ARG EMBED_MODEL=all-MiniLM-L6-v2
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBED_MODEL}')"

# 3. The application code.
COPY config.py observability.py rag.py app.py ./
COPY static ./static

# 4. Run as a normal user, not root. /data holds the vector database (a volume).
RUN useradd --create-home appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data /opt/hf
USER appuser

VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
