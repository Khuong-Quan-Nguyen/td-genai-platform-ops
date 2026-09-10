"""Pydantic schemas for the TD GenAI Platform API."""
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ContextDomain(str, Enum):
    """Prompt context the assistant operates under."""

    GENERAL = "general"
    FINANCIAL_SERVICES = "financial-services"


class PIIMatch(BaseModel):
    """A single piece of PII located in user input."""

    kind: str = Field(..., description="Detector that fired, e.g. 'sin' or 'credit_card'")
    redacted: str = Field(..., description="Masked form safe for logs and UI")
    start: int
    end: int


class CodeAssistRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=8000)
    user_id: str = Field(..., min_length=1, max_length=128)
    context: ContextDomain = ContextDomain.GENERAL


class CodeAssistResponse(BaseModel):
    audit_id: str
    user_id: str
    response: str
    tokens_used: int
    input_tokens: int
    output_tokens: int
    pii_detected: bool
    pii_matches: list[PIIMatch] = []
    model: str
    latency_ms: int
    timestamp: datetime


class AuditRecord(BaseModel):
    """One row of the audit trail. Never contains raw PII."""

    audit_id: str
    user_id: str
    status: Literal["success", "blocked", "error"]
    pii_detected: bool
    pii_kinds: list[str] = []
    context: ContextDomain
    tokens_used: int
    latency_ms: int
    timestamp: datetime
    detail: str | None = None


class AuditTrailResponse(BaseModel):
    count: int
    records: list[AuditRecord]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    model: str
    api_key_configured: bool
