"""TD GenAI Platform - FastAPI application.

Serves the JSON API under /api/v1 and the compiled React SPA at the root, so a
single Azure App Service instance hosts both.
"""
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

import agent  # noqa: E402  - must follow load_dotenv so env vars are visible
import audit  # noqa: E402
import security  # noqa: E402
from models import (  # noqa: E402
    AuditTrailResponse,
    CodeAssistRequest,
    CodeAssistResponse,
    HealthResponse,
)

VERSION = "0.1.0"
STATIC_DIR = Path(__file__).parent / "static"

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("td-genai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    loaded = audit.load_from_disk()
    log.info("audit trail rehydrated: %d records", loaded)
    if not os.getenv("ANTHROPIC_API_KEY"):
        log.warning("ANTHROPIC_API_KEY is unset - /api/v1/code-assist will return 503")
    yield


app = FastAPI(
    title="TD GenAI Platform",
    version=VERSION,
    description="PII-guarded Claude access with a full audit trail.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


router = APIRouter()


@router.get("/v1/health", response_model=HealthResponse, tags=["ops"])
def health() -> HealthResponse:
    configured = bool(os.getenv("ANTHROPIC_API_KEY"))
    return HealthResponse(
        status="ok" if configured else "degraded",
        version=VERSION,
        model=agent.MODEL,
        api_key_configured=configured,
    )


@router.post("/v1/code-assist", response_model=CodeAssistResponse, tags=["assistant"])
def code_assist(request: CodeAssistRequest) -> CodeAssistResponse:
    """Redact PII, call Claude, and write exactly one audit record."""
    audit_id = audit.new_audit_id()
    started = time.perf_counter()

    redacted, matches = security.scan(request.query)
    kinds = sorted({match.kind for match in matches})

    try:
        result = agent.run(redacted, request.context)
    except agent.AgentError as exc:
        elapsed = int((time.perf_counter() - started) * 1000)
        audit.record(
            audit_id=audit_id,
            user_id=request.user_id,
            status="error",
            pii_detected=bool(matches),
            pii_kinds=kinds,
            context=request.context,
            tokens_used=0,
            latency_ms=elapsed,
            detail=str(exc),
        )
        log.error("code-assist %s failed: %s", audit_id, exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    elapsed = int((time.perf_counter() - started) * 1000)
    audit.record(
        audit_id=audit_id,
        user_id=request.user_id,
        status="success",
        pii_detected=bool(matches),
        pii_kinds=kinds,
        context=request.context,
        tokens_used=result.total_tokens,
        latency_ms=elapsed,
    )

    return CodeAssistResponse(
        audit_id=audit_id,
        user_id=request.user_id,
        response=result.text,
        tokens_used=result.total_tokens,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        pii_detected=bool(matches),
        pii_matches=matches,
        model=result.model,
        latency_ms=elapsed,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/v1/audit-trail", response_model=AuditTrailResponse, tags=["ops"])
def audit_trail(limit: int = 100) -> AuditTrailResponse:
    records = audit.recent(min(max(limit, 1), 500))
    return AuditTrailResponse(count=len(records), records=records)


# --- Router mounting ---------------------------------------------------------
# Serverless hosts differ in what path the function receives: some pass the
# full request path, others strip the prefix that selected the function. The
# router is therefore mounted at both, so the same build works locally, in a
# container, and on Vercel. Only the canonical /api prefix is documented.

app.include_router(router, prefix="/api", tags=["api"])
app.include_router(router, include_in_schema=False)


# --- Static SPA -------------------------------------------------------------
# Mounted last so /api/v1 routes always win. The catch-all returns index.html
# for unknown paths, letting React Router own client-side navigation.

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    if (STATIC_DIR / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (STATIC_DIR / full_path).resolve()
        if full_path and candidate.is_file() and STATIC_DIR.resolve() in candidate.parents:
            return FileResponse(candidate)
        index = STATIC_DIR / "index.html"
        if index.is_file():
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="Frontend not built")
else:
    @app.get("/", include_in_schema=False)
    def no_frontend():
        return {
            "detail": "Frontend not built. Run: cd frontend && npm install && npm run build",
            "api_docs": "/docs",
        }
