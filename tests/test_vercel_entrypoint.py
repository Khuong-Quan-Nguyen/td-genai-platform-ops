"""Vercel deployment-shape tests.

Vercel's zero-config FastAPI detection picks up the root-level main.py and runs
`main.app` as one function that receives the caller's real path. A rewrite of
/api/* onto another path lands every API call on the SPA catch-all instead -
GETs 404 and POSTs 405 - while every test against `main.app` still passes.
These cases pin the config so that regression is caught in CI.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERCEL = json.loads((ROOT / "vercel.json").read_text())


def test_no_rewrite_touches_api_paths():
    for rule in VERCEL.get("rewrites", []):
        assert not rule["source"].startswith("/api"), rule
        assert not rule["destination"].startswith("/api"), rule


def test_function_config_targets_the_detected_entrypoint():
    """Vercel keys function settings by the resolved entrypoint file."""
    assert set(VERCEL.get("functions", {})) == {"main.py"}


def test_no_competing_api_directory_function():
    """Any .py under api/ becomes its own function and can shadow main.app."""
    assert not list((ROOT / "api").glob("*.py"))
