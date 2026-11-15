"""
Logging and metrics in one place.

Logs:    one JSON object per line on stdout (Docker collects stdout).
Metrics: Prometheus counters / histograms / gauges, exposed at GET /metrics.
"""
import contextvars
import json
import logging
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from prometheus_client import Counter, Gauge, Histogram

from config import LOG_LEVEL

# The id of the HTTP request being handled, so every log line can carry it.
request_id = contextvars.ContextVar("request_id", default=None)

logger = logging.getLogger("rag")


# ---------------------------- Logging ----------------------------
class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        if request_id.get():
            entry["request_id"] = request_id.get()
        entry.update(getattr(record, "fields", {}))
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def setup_logging():
    """Send every log (ours, uvicorn's, libraries') to stdout as JSON."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(LOG_LEVEL)

    for name in ("uvicorn", "uvicorn.error"):
        uv = logging.getLogger(name)
        uv.handlers = []
        uv.propagate = True
    # We log each request ourselves (with duration and request id).
    logging.getLogger("uvicorn.access").disabled = True
    # Libraries that log every outgoing HTTP call: keep only their warnings.
    for name in ("httpx", "httpx2", "httpcore", "google_genai", "sentence_transformers"):
        logging.getLogger(name).setLevel(logging.WARNING)
    # Progress bars are not JSON and would clutter the log stream.
    try:
        from transformers.utils import logging as hf_logging
        hf_logging.disable_progress_bar()
    except ImportError:
        pass


def log_event(event, level=logging.INFO, exc_info=False, **fields):
    """log_event("document_indexed", doc_id="ab12", chunks=5)"""
    logger.log(level, event, exc_info=exc_info, extra={"fields": fields})


# ---------------------------- Metrics ----------------------------
_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60)

HTTP_REQUESTS = Counter(
    "http_requests_total", "HTTP requests handled", ["method", "path", "status"]
)
HTTP_SECONDS = Histogram(
    "http_request_duration_seconds", "HTTP request duration", ["method", "path"],
    buckets=_BUCKETS,
)
STEP_SECONDS = Histogram(
    "rag_step_duration_seconds",
    "Duration of one pipeline step (load, chunk, embed, store, retrieve, generate)",
    ["step"], buckets=_BUCKETS,
)
QUESTIONS = Counter("rag_questions_total", "Questions answered")
GEMINI_ERRORS = Counter("rag_gemini_errors_total", "Failed Gemini calls", ["code"])
GEMINI_TOKENS = Counter("rag_gemini_tokens_total", "Gemini tokens used", ["type"])
UPLOAD_BYTES = Histogram(
    "rag_upload_bytes", "Size of indexed PDFs in bytes",
    buckets=(1e4, 1e5, 5e5, 1e6, 5e6, 1e7, 2.5e7, 5e7),
)
DOCUMENTS = Gauge("rag_documents", "Documents currently indexed")
CHUNKS = Gauge("rag_chunks", "Chunks currently indexed")


# Create the labelled series at zero now. A series that first appears with a
# value already above zero would be missed by Prometheus rate()/increase().
for _step in ("load", "chunk", "embed", "store", "retrieve", "generate"):
    STEP_SECONDS.labels(_step)
for _type in ("input", "output"):
    GEMINI_TOKENS.labels(type=_type)


@contextmanager
def timed(step, timings=None):
    """Time a pipeline step. Records the metric and, if given a dict,
    stores the duration in milliseconds under `<step>_ms` for logging."""
    start = time.perf_counter()
    try:
        yield
    finally:
        seconds = time.perf_counter() - start
        STEP_SECONDS.labels(step).observe(seconds)
        if timings is not None:
            timings[f"{step}_ms"] = round(seconds * 1000, 1)
