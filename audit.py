"""Append-only audit trail.

Every request produces exactly one record whether it succeeds, is blocked, or
errors. Records carry PII *kinds*, never PII values.

Two storage backends, chosen at import time:

- **Postgres** when ``DATABASE_URL`` is set. Required on serverless hosts
  (Vercel, Lambda), where the filesystem is ephemeral and each request may hit
  a different instance - a file-backed trail there silently loses records.
- **JSONL file** otherwise. Fine for local development and single-instance
  containers with a mounted volume.

The in-memory deque is a read cache for the dashboard, not the system of
record. On Postgres it is bypassed for reads so every instance sees the same
trail.
"""
import json
import os
import threading
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from models import AuditRecord, ContextDomain

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL)

AUDIT_LOG_PATH = Path(os.getenv("AUDIT_LOG_PATH", "audit-trail.jsonl"))
MAX_IN_MEMORY = int(os.getenv("AUDIT_MEMORY_LIMIT", "500"))

_lock = threading.Lock()
_recent: deque[AuditRecord] = deque(maxlen=MAX_IN_MEMORY)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS audit_trail (
    audit_id     TEXT PRIMARY KEY,
    user_id      TEXT        NOT NULL,
    status       TEXT        NOT NULL,
    pii_detected BOOLEAN     NOT NULL,
    pii_kinds    TEXT[]      NOT NULL DEFAULT '{}',
    context      TEXT        NOT NULL,
    tokens_used  INTEGER     NOT NULL DEFAULT 0,
    latency_ms   INTEGER     NOT NULL DEFAULT 0,
    timestamp    TIMESTAMPTZ NOT NULL,
    detail       TEXT
);
CREATE INDEX IF NOT EXISTS audit_trail_timestamp_idx
    ON audit_trail (timestamp DESC);
"""


def new_audit_id() -> str:
    return f"aud_{uuid.uuid4().hex[:16]}"


# --- Postgres backend -------------------------------------------------------

def _connect():
    """Open a short-lived connection.

    Serverless invocations are too short-lived to benefit from a pool, and a
    pool held across freezes leaks connections. Point DATABASE_URL at a pooler
    (Neon's -pooler host, PgBouncer) so this stays cheap.
    """
    import psycopg  # imported lazily so local runs need no driver

    return psycopg.connect(DATABASE_URL, connect_timeout=10)


_schema_ready = False


def _ensure_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE)
        conn.commit()
    _schema_ready = True


def _pg_write(entry: AuditRecord) -> None:
    _ensure_schema()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_trail (
                    audit_id, user_id, status, pii_detected, pii_kinds,
                    context, tokens_used, latency_ms, timestamp, detail
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (audit_id) DO NOTHING
                """,
                (
                    entry.audit_id,
                    entry.user_id,
                    entry.status,
                    entry.pii_detected,
                    entry.pii_kinds,
                    entry.context.value,
                    entry.tokens_used,
                    entry.latency_ms,
                    entry.timestamp,
                    entry.detail,
                ),
            )
        conn.commit()


def _pg_read(limit: int) -> list[AuditRecord]:
    _ensure_schema()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT audit_id, user_id, status, pii_detected, pii_kinds,
                       context, tokens_used, latency_ms, timestamp, detail
                FROM audit_trail
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return [
        AuditRecord(
            audit_id=r[0],
            user_id=r[1],
            status=r[2],
            pii_detected=r[3],
            pii_kinds=list(r[4] or []),
            context=ContextDomain(r[5]),
            tokens_used=r[6],
            latency_ms=r[7],
            timestamp=r[8],
            detail=r[9],
        )
        for r in rows
    ]


# --- Public API -------------------------------------------------------------

def record(
    *,
    audit_id: str,
    user_id: str,
    status: Literal["success", "blocked", "error"],
    pii_detected: bool,
    pii_kinds: list[str],
    context: ContextDomain,
    tokens_used: int,
    latency_ms: int,
    detail: str | None = None,
) -> AuditRecord:
    entry = AuditRecord(
        audit_id=audit_id,
        user_id=user_id,
        status=status,
        pii_detected=pii_detected,
        pii_kinds=pii_kinds,
        context=context,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
        timestamp=datetime.now(timezone.utc),
        detail=detail,
    )

    with _lock:
        _recent.appendleft(entry)

    if USE_POSTGRES:
        # A durable audit record is the point of this service: if the write
        # fails, the caller must know rather than get a response that was
        # never logged.
        _pg_write(entry)
        return entry

    with _lock:
        try:
            with AUDIT_LOG_PATH.open("a", encoding="utf-8") as handle:
                handle.write(entry.model_dump_json() + "\n")
        except OSError:
            # Local/dev fallback: an unwritable file must not fail the request;
            # the in-memory trail still reflects the event.
            pass
    return entry


def recent(limit: int = 100) -> list[AuditRecord]:
    if USE_POSTGRES:
        return _pg_read(limit)
    with _lock:
        return list(_recent)[:limit]


def load_from_disk() -> int:
    """Rehydrate the in-memory trail on startup. Returns rows loaded.

    No-op on Postgres, where reads go straight to the database.
    """
    if USE_POSTGRES:
        _ensure_schema()
        return 0
    if not AUDIT_LOG_PATH.exists():
        return 0
    rows: list[AuditRecord] = []
    with AUDIT_LOG_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(AuditRecord(**json.loads(line)))
            except (json.JSONDecodeError, ValueError):
                continue
    with _lock:
        _recent.clear()
        for entry in rows[-MAX_IN_MEMORY:]:
            _recent.appendleft(entry)
    return len(rows)
