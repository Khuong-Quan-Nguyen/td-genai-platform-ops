"""Vercel entrypoint tests.

A Vercel rewrite replaces the request path with the function's own path, so
without the RestoreOriginalPath middleware every API call 404s in production
while passing every local test. These cases simulate the rewritten request
shape so that regression is caught in CI.
"""
import pytest
from fastapi.testclient import TestClient

from api.index import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_through_rewrite(client):
    r = client.get("/api/index", params={"__path": "v1/health"})
    assert r.status_code == 200
    assert r.json()["version"]


def test_audit_trail_through_rewrite(client):
    r = client.get("/api/index", params={"__path": "v1/audit-trail"})
    assert r.status_code == 200
    assert "records" in r.json()


def test_leading_slash_in_path_param(client):
    """Vercel's $1 capture may or may not carry a leading slash."""
    r = client.get("/api/index", params={"__path": "/v1/health"})
    assert r.status_code == 200


def test_caller_query_params_survive(client):
    r = client.get("/api/index", params={"__path": "v1/audit-trail", "limit": "3"})
    assert r.status_code == 200


def test_unknown_route_still_404s(client):
    r = client.get("/api/index", params={"__path": "v1/does-not-exist"})
    assert r.status_code == 404


def test_post_body_survives_rewrite(client, monkeypatch):
    """The rewrite must not disturb the request body."""
    import agent
    from models import ContextDomain

    def _run(query, context=ContextDomain.GENERAL):
        return agent.AgentResult(text="ok", input_tokens=1, output_tokens=1,
                                 model="claude-opus-5")

    monkeypatch.setattr(agent, "run", _run)
    r = client.post(
        "/api/index",
        params={"__path": "v1/code-assist"},
        json={"query": "hello", "user_id": "u1"},
    )
    assert r.status_code == 200
    assert r.json()["response"] == "ok"
