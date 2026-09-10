# TD GenAI Platform — Ops MVP

Governed Claude access for TD engineering: a PII guardrail and an append-only
audit trail in front of every model call, with a React ops console served from
the same FastAPI process.

## Architecture

```
Browser ──> FastAPI (single port 8000)
             ├── /                → React SPA (built into ./static)
             ├── /api/v1/health         → liveness, model, key status
             ├── /api/v1/code-assist    → redact → Claude → audit
             └── /api/v1/audit-trail    → recent audit records
```

Request path for `code-assist`:

1. `security.scan()` finds and redacts PII (SIN, credit card, bank account,
   email, phone). Raw identifiers never leave the process.
2. `agent.run()` sends the **redacted** text to Claude Opus 5.
3. `audit.record()` writes exactly one row — success, blocked, or error —
   carrying PII *kinds*, never PII values.

| File | Role |
|---|---|
| `main.py` | FastAPI app, API routes, static SPA mounting |
| `models.py` | Pydantic request/response schemas |
| `security.py` | PII detection and redaction |
| `agent.py` | Claude API layer |
| `audit.py` | Append-only audit trail (JSONL + in-memory) |
| `frontend/` | React + Vite source |
| `static/` | Built SPA (generated — do not edit) |

## Local development

```bash
# 1. Backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt

# 2. Frontend
cd frontend && npm install && npm run build && cd ..

# 3. Configure
cp .env.example .env      # then set ANTHROPIC_API_KEY

# 4. Run
.venv/Scripts/python.exe -m uvicorn main:app --reload --port 8000
```

Open <http://127.0.0.1:8000>. API docs at `/docs`.

For frontend hot-reload, run the backend on 8000 and `npm run dev` in
`frontend/` — Vite proxies `/api` to the backend on port 5173.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Required.** Claude API credential |
| `ANTHROPIC_MODEL` | `claude-opus-5` | Model id |
| `ANTHROPIC_MAX_TOKENS` | `8000` | Output cap |
| `ANTHROPIC_EFFORT` | `high` | Thinking depth (`low`–`max`) |
| `AUDIT_LOG_PATH` | `audit-trail.jsonl` | Audit log location |
| `AUDIT_MEMORY_LIMIT` | `500` | In-memory record cap |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated origins |
| `LOG_LEVEL` | `INFO` | Python log level |

## API

**`POST /api/v1/code-assist`**

```json
{ "query": "...", "user_id": "qnguyen", "context": "financial-services" }
```

Returns `audit_id`, `response`, `tokens_used`, `input_tokens`, `output_tokens`,
`pii_detected`, `pii_matches`, `model`, `latency_ms`, `timestamp`.
`context` is `general` or `financial-services`.

**`GET /api/v1/audit-trail?limit=100`** — newest first.

**`GET /api/v1/health`** — `status` is `degraded` when no API key is configured.

## Docker

```bash
docker build -t td-genai-platform-ops .
docker run -p 8000:8000 --env-file .env td-genai-platform-ops
```

Multi-stage: Node 22 builds the SPA, Python 3.13-slim runs it as non-root
`appuser`. Mount a volume at `/app/data` to persist the audit log.

## Azure App Service

`.github/workflows/deploy.yml` runs tests, pushes the image to GHCR, and
deploys on every push to `main`. Required repository secrets:

- `AZURE_WEBAPP_PUBLISH_PROFILE` — from the App Service **Get publish profile** button

Set `ANTHROPIC_API_KEY` in App Service → Configuration → Application settings
(not in the image). App Service injects `$PORT`; the container honours it.

## Known gaps (MVP)

- Audit trail is file-backed, not a database — fine for a single instance,
  needs Postgres or Azure Table Storage before scale-out.
- No authentication on the API; App Service Easy Auth or APIM sits in front.
- PII detectors are regex + Luhn. They catch the common Canadian formats but
  are not a substitute for a full DLP scan.
