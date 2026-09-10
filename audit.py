"""Append-only audit trail.

Every request produces exactly one record whether it succeeds, is blocked, or
errors. Records are written to a JSONL file for durability and kept in a bounded
in-memory deque so the dashboard can read recent activity without file I/O.

Records carry PII *kinds*, never PII values.
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

AUDIT_LOG_PATH = Path(os.getenv("AUDIT_LOG_PATH", "audit-trail.jsonl"))
MAX_IN_MEMORY = int(os.getenv("AUDIT_MEMORY_LIMIT", "500"))

_lock = threading.Lock()
_recent: deque[AuditRecord] = deque(maxlen=MAX_IN_MEMORY)


def new_audit_id() -> str:
    return f"aud_{uuid.uuid4().hex[:16]}"


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
        try:
            with AUDIT_LOG_PATH.open("a", encoding="utf-8") as handle:
                handle.write(entry.model_dump_json() + "\n")
        except OSError:
            # An unwritable log must not fail the request; the in-memory trail
            # still reflects the event and the container logs the failure.
            pass
    return entry


def recent(limit: int = 100) -> list[AuditRecord]:
    with _lock:
        return list(_recent)[:limit]


def load_from_disk() -> int:
    """Rehydrate the in-memory trail on startup. Returns rows loaded."""
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
