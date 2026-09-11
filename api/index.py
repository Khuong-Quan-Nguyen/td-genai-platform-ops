"""Vercel serverless entrypoint.

Vercel's Python runtime looks for a module-level ASGI app named `app`.

Path handling: a Vercel rewrite can replace the request path with the
function's own path, which would make FastAPI see `/api/index` for every
request and match nothing. `vercel.json` forwards the real path as a `__path`
query parameter; the middleware below restores it into the ASGI scope before
routing, preserving the caller's own query parameters.

`VERCEL_DIAG=1` enables a catch-all that reports what the function actually
received - used to diagnose routing, then turned off.
"""
import os
import pathlib
import sys
from urllib.parse import parse_qs, urlencode

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi import Request  # noqa: E402

from main import app as _app  # noqa: E402

_PATH_PARAM = "__path"


class RestoreOriginalPath:
    """Undo Vercel's rewrite so FastAPI sees the caller's real path."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            params = parse_qs(scope.get("query_string", b"").decode(), keep_blank_values=True)
            original = params.pop(_PATH_PARAM, [None])[0]
            if original is not None:
                path = "/api/" + original.lstrip("/")
                scope = dict(scope)
                scope["path"] = path
                scope["raw_path"] = path.encode()
                scope["query_string"] = urlencode(params, doseq=True).encode()
        await self.inner(scope, receive, send)


if os.getenv("VERCEL_DIAG") == "1":

    @_app.api_route("/{diag_path:path}", methods=["GET"], include_in_schema=False)
    async def _diagnose(request: Request, diag_path: str):
        """Report what reached the function. Never returns secrets."""
        return {
            "diagnostic": True,
            "received_path": request.url.path,
            "query_string": str(request.url.query),
            "root_path": request.scope.get("root_path"),
            "middleware_active": True,
            "vercel_headers": {
                k: v for k, v in request.headers.items() if k.lower().startswith("x-vercel")
            },
            "env": {
                "has_api_key": bool(os.getenv("ANTHROPIC_API_KEY")),
                "has_database_url": bool(os.getenv("DATABASE_URL")),
                "effort": os.getenv("ANTHROPIC_EFFORT"),
            },
        }


app = RestoreOriginalPath(_app)
