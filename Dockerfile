# syntax=docker/dockerfile:1

# --- Stage 1: build the React SPA -------------------------------------------
FROM node:22-alpine AS frontend

WORKDIR /build

# Copy manifests first so `npm ci` is cached independently of source changes.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# vite.config.js writes to ../static, so give it a directory to land in.
RUN mkdir -p /static && npm run build -- --outDir /static --emptyOutDir


# --- Stage 2: python runtime ------------------------------------------------
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py models.py security.py agent.py audit.py ./
COPY --from=frontend /static ./static

# Audit log lives on a writable path; mount a volume here to persist it.
ENV AUDIT_LOG_PATH=/app/data/audit-trail.jsonl
RUN mkdir -p /app/data && \
    adduser --disabled-password --gecos "" --uid 10001 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health').status==200 else 1)"

# Azure App Service injects $PORT; default to 8000 for local runs.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
