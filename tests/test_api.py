"""API and audit-trail tests.

`agent.run` is monkeypatched throughout, so no API key and no network call is
needed. What's under test is the wiring: redaction happens before the model
sees the text, and exactly one audit record is written per request.
"""
import pytest
from fastapi.testclient import TestClient

import agent
import audit
import main
from models import ContextDomain


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "AUDIT_LOG_PATH", tmp_path / "audit.jsonl")
    audit._recent.clear()
    return TestClient(main.app)


@pytest.fixture
def fake_agent(monkeypatch):
    """Capture what the agent layer receives, and return a canned result."""
    seen = {}

    def _run(query, context=ContextDomain.GENERAL):
        seen["query"] = query
        seen["context"] = context
        return agent.AgentResult(
            text="Here is a retry decorator.",
            input_tokens=120,
            output_tokens=45,
            model="claude-opus-5",
        )

    monkeypatch.setattr(agent, "run", _run)
    return seen


def test_health(client):
    body = client.get("/api/v1/health").json()
    assert body["status"] in {"ok", "degraded"}
    assert body["version"] == main.VERSION


def test_code_assist_success(client, fake_agent):
    response = client.post(
        "/api/v1/code-assist",
        json={"query": "Write a retry decorator", "user_id": "qnguyen"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tokens_used"] == 165
    assert body["pii_detected"] is False
    assert body["audit_id"].startswith("aud_")


def test_pii_redacted_before_reaching_agent(client, fake_agent):
    """The critical guarantee: raw PII never reaches the model."""
    response = client.post(
        "/api/v1/code-assist",
        json={"query": "My SIN is 046 454 286, help me", "user_id": "qnguyen"},
    )
    assert response.status_code == 200
    assert "046 454 286" not in fake_agent["query"]
    assert "[REDACTED_SIN]" in fake_agent["query"]
    assert response.json()["pii_detected"] is True


def test_audit_record_written_on_success(client, fake_agent):
    client.post(
        "/api/v1/code-assist",
        json={"query": "hello", "user_id": "qnguyen"},
    )
    records = client.get("/api/v1/audit-trail").json()["records"]
    assert len(records) == 1
    assert records[0]["status"] == "success"
    assert records[0]["user_id"] == "qnguyen"


def test_audit_record_written_on_failure(client, monkeypatch):
    def _boom(query, context=ContextDomain.GENERAL):
        raise agent.AgentError("API key is invalid.")

    monkeypatch.setattr(agent, "run", _boom)
    response = client.post(
        "/api/v1/code-assist",
        json={"query": "My SIN is 046 454 286", "user_id": "qnguyen"},
    )
    assert response.status_code == 503

    records = client.get("/api/v1/audit-trail").json()["records"]
    assert len(records) == 1, "a failed request must still be audited"
    assert records[0]["status"] == "error"
    assert records[0]["pii_detected"] is True
    assert records[0]["tokens_used"] == 0


def test_audit_never_contains_raw_pii(client, fake_agent):
    client.post(
        "/api/v1/code-assist",
        json={"query": "SIN 046 454 286 card 4532015112830366", "user_id": "u1"},
    )
    body = client.get("/api/v1/audit-trail").text
    assert "046 454 286" not in body
    assert "4532015112830366" not in body


def test_financial_context_forwarded(client, fake_agent):
    client.post(
        "/api/v1/code-assist",
        json={
            "query": "hello",
            "user_id": "u1",
            "context": "financial-services",
        },
    )
    assert fake_agent["context"] == ContextDomain.FINANCIAL_SERVICES


@pytest.mark.parametrize(
    "payload",
    [
        {"query": "", "user_id": "u1"},
        {"query": "hi"},
        {"user_id": "u1"},
        {"query": "hi", "user_id": "u1", "context": "not-a-context"},
    ],
)
def test_validation_rejects_bad_payloads(client, payload):
    assert client.post("/api/v1/code-assist", json=payload).status_code == 422


def test_unknown_api_route_is_404_not_spa(client):
    """The SPA catch-all must never swallow a bad API path."""
    assert client.get("/api/v1/does-not-exist").status_code == 404
