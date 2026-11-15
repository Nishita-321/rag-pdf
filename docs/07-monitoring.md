# Step 5: logging and Grafana

The app now reports what it is doing in two ways, and Grafana shows both.

| | Answers | Example |
|---|---------|---------|
| **Logs** | What happened in this one request? | "Question on doc `1349…` took 3.4 s, 771 input tokens" |
| **Metrics** | How is the app doing overall? | "95% of questions are answered within 6 s" |

## Run

```bash
docker compose --profile monitoring up -d --build
```

| URL | What | Login |
|-----|------|-------|
| http://localhost:8000 | The app | |
| http://localhost:3000 | Grafana, opens on the **RAG PDF** dashboard | `admin` / `admin` |
| http://localhost:9090 | Prometheus (raw metrics, for debugging) | |

Monitoring is optional. Plain `docker compose up -d` still starts only the app.

| Command | Does |
|---------|------|
| `docker compose --profile monitoring up -d` | Start app + monitoring |
| `docker compose --profile monitoring down` | Stop everything. Without `--profile monitoring`, the monitoring containers keep running |
| `GRAFANA_PASSWORD=secret docker compose --profile monitoring up -d` | Set the Grafana admin password on first start |
| `GRAFANA_PORT=3001 docker compose --profile monitoring up -d` | Use another port for Grafana |

## How it fits together

```
app ── /metrics ──────────────> Prometheus ──┐
app ── stdout (JSON logs) ──> Alloy ──> Loki ├──> Grafana
```

| Container | Job |
|-----------|-----|
| `app` | Writes JSON logs to stdout, exposes numbers at `/metrics` |
| `prometheus` | Reads `/metrics` every 15 seconds and stores the history |
| `alloy` | Reads this project's container logs from Docker and sends them to Loki |
| `loki` | Stores logs and makes them searchable |
| `grafana` | Dashboards over Prometheus, log search over Loki |

## Files

| File | Role |
|------|------|
| `observability.py` | JSON log format, metric definitions, the `timed()` helper |
| `app.py` | Middleware that times, counts and logs every request; `/metrics` endpoint |
| `rag.py` | Times each pipeline step; logs indexing, questions and Gemini errors |
| `monitoring/prometheus.yml` | Tells Prometheus to scrape `app:8000` |
| `monitoring/alloy.alloy` | Tells Alloy which container logs to ship |
| `monitoring/grafana/provisioning/` | Connects Grafana to Prometheus and Loki automatically |
| `monitoring/grafana/dashboards/rag-pdf.json` | The dashboard |

## Logs

Every log line is one JSON object:

```json
{"ts": "2026-11-15T09:45:50.053+00:00", "level": "INFO", "logger": "rag",
 "event": "question_answered", "request_id": "d7d4f3334fcf", "doc_id": "all",
 "question_chars": 19, "chunks": 4, "pages": [1, 1, 2, 2], "model": "gemini-3.5-flash",
 "input_tokens": 710, "output_tokens": 127, "retrieve_ms": 32.8, "generate_ms": 5210.4}
```

| Event | When | Main fields |
|-------|------|-------------|
| `app_started` | Server start | `llm_model`, `gemini_key_set` |
| `request` | Every HTTP request | `method`, `path`, `status`, `duration_ms` |
| `document_indexed` | Upload finished | `doc_id`, `name`, `pages`, `chunks`, `bytes`, `load_ms`, `chunk_ms`, `embed_ms`, `store_ms` |
| `question_answered` | Answer returned | `doc_id`, `question_chars`, `pages`, `input_tokens`, `output_tokens`, `retrieve_ms`, `generate_ms` |
| `document_deleted` | Document removed | `doc_id` |
| `gemini_error` | Gemini call failed | `code`, `message`, `model` |
| `unhandled_error` | A bug | `exception` (the stack trace) |

**Request id.** Each request gets a short id. It is on every log line written during that request and returned in the `X-Request-ID` response header, so all lines for one request can be found together.

**Privacy.** The question text is not logged, only its length. Set `LOG_QUESTIONS=true` in `.env` to include it. API keys are never logged.

**Not logged:** `/health` and `/metrics` requests. They are polled constantly and would drown everything else. They are still counted in the metrics.

| Setting | Default | Meaning |
|---------|---------|---------|
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR` |
| `LOG_QUESTIONS` | `false` | Include the question text in `question_answered` |

Without Grafana, the same logs are available with `docker compose logs -f app`.

### Searching logs in Grafana

Go to **Explore**, choose **Loki**, and enter a query:

| Query | Finds |
|-------|-------|
| `{service="app"}` | All app logs |
| `{service="app"} \| json \| level="ERROR"` | Errors |
| `{service="app"} \| json \| request_id="d7d4f3334fcf"` | Everything from one request |
| `{service="app"} \| json \| event="question_answered" \| generate_ms > 5000` | Questions where Gemini took over 5 s |
| `{service="app"} \| json \| status >= 400` | Failed requests |

## Metrics

All available at `GET /metrics`.

| Metric | Type | Labels | Meaning |
|--------|------|--------|---------|
| `http_requests_total` | Counter | `method`, `path`, `status` | Requests handled |
| `http_request_duration_seconds` | Histogram | `method`, `path` | How long requests took |
| `rag_step_duration_seconds` | Histogram | `step` | Time per pipeline step: `load`, `chunk`, `embed`, `store`, `retrieve`, `generate` |
| `rag_questions_total` | Counter | | Questions answered |
| `rag_gemini_tokens_total` | Counter | `type` (`input`, `output`) | Tokens used, which is what Gemini bills |
| `rag_gemini_errors_total` | Counter | `code` | Failed Gemini calls by HTTP code |
| `rag_upload_bytes` | Histogram | | Size of indexed PDFs |
| `rag_documents` | Gauge | | Documents currently indexed |
| `rag_chunks` | Gauge | | Chunks currently indexed |

The three types:

| Type | Behaviour | Read it with |
|------|-----------|--------------|
| Counter | Only goes up | `rate(...)` for per-second, `increase(...)` for a total over a period |
| Gauge | Goes up and down | The value itself |
| Histogram | Counts observations in size buckets | `histogram_quantile(0.95, ...)` for percentiles |

The `path` label is the route template (`/documents/{doc_id}`), not the real URL. Otherwise every document would create its own series.

## The dashboard

| Row | Panels |
|-----|--------|
| Overview | Documents, chunks, questions answered, tokens used, server errors, Gemini errors |
| HTTP requests | Requests per second and 95th-percentile response time by endpoint, responses by status, Gemini errors by code |
| RAG pipeline | Average time per step, tokens per minute |
| Logs | Errors and warnings, then all app logs |

Reading it:

- **A slow `/ask`** is almost always the `generate` step, which is the Gemini call. `retrieve` takes milliseconds.
- **A slow upload** is the `embed` step, and grows with the size of the PDF.
- **Gemini error codes:** `429` is the rate limit, `400`/`403` a bad key, `404` a wrong model name.
- Panels need a minute of data after the first start, and stay empty until the app gets some requests.

The dashboard can be edited in Grafana, but the file is reloaded on restart. To keep a change, export the dashboard JSON and save it over `monitoring/grafana/dashboards/rag-pdf.json`.

## Limits

| Limit | Effect |
|-------|--------|
| Grafana password defaults to `admin` | Fine on your machine, where ports 3000 and 9090 are open to `localhost` only. Set `GRAFANA_PASSWORD` anywhere else |
| `GRAFANA_PASSWORD` only applies on first start | Later, change the password inside Grafana |
| No alerts | Nothing notifies you when errors rise; you have to look |
| Logs are kept forever | Loki has no retention configured, so its volume grows slowly |
| Metrics are kept 15 days | Prometheus's default |
| Counters restart at zero with the app | Graphs handle this; the raw numbers at `/metrics` do not |
| Alloy reads the Docker socket | It can see all containers on the machine. It is mounted read-only and filtered to this project |
| About 1.7 GB of extra images | Prometheus, Loki, Alloy and Grafana |

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Dashboard panels say "No data" | No requests yet, or under a minute since start | Use the app, wait, refresh |
| Metric panels empty, logs fine | Prometheus cannot reach the app | Open http://localhost:9090/targets; `rag-pdf` should be `UP` |
| Log panels empty | Alloy cannot read Docker logs | `docker compose logs alloy` |
| `port is already allocated` on 3000 | Another program uses the port | `GRAFANA_PORT=3001 docker compose --profile monitoring up -d` |
| Monitoring still running after `down` | `down` was run without the profile | `docker compose --profile monitoring down` |
