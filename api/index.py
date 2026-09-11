"""Vercel serverless entrypoint.

Vercel's Python runtime looks for a module-level ASGI app named `app`. The
real application lives at the repo root, so put the root on sys.path and
re-export it.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from main import app  # noqa: E402,F401  - re-exported for the Vercel runtime
