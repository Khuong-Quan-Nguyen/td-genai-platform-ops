"""Agent configuration tests.

Hosting dashboards make it easy to save a variable with an empty value, and
os.getenv returns "" rather than its default in that case. An empty model id
reaches the API as model="" and every request fails.
"""
import importlib

import pytest

import agent


@pytest.fixture
def reload_agent(monkeypatch):
    def _reload(**env):
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        return importlib.reload(agent)

    yield _reload
    monkeypatch.undo()
    importlib.reload(agent)


def test_empty_env_vars_fall_back_to_defaults(reload_agent):
    mod = reload_agent(ANTHROPIC_MODEL="", ANTHROPIC_MAX_TOKENS="", ANTHROPIC_EFFORT="")
    assert mod.MODEL == "claude-opus-5"
    assert mod.MAX_TOKENS == 8000
    assert mod.EFFORT == "high"


def test_set_env_vars_are_honoured(reload_agent):
    mod = reload_agent(
        ANTHROPIC_MODEL="claude-sonnet-5",
        ANTHROPIC_MAX_TOKENS="1234",
        ANTHROPIC_EFFORT="medium",
    )
    assert mod.MODEL == "claude-sonnet-5"
    assert mod.MAX_TOKENS == 1234
    assert mod.EFFORT == "medium"
