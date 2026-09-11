"""Vercel serverless entrypoint.

Vercel's Python runtime looks for a module-level ASGI app named `app`.

Serverless hosts differ in what path the function receives. Two defences:

1. `vercel.json` forwards the real path as a `__path` query parameter, which
   `RestoreOriginalPath` puts back into the ASGI scope.
2. `main.py` mounts the API router at both `/api/v1` and `/v1`.

A last-resort catch-all reports what actually arrived, so a routing mismatch
is diagnosable from the response instead of guessed at. It is registered after
every real route, so it only ever sees requests nothing else matched.
"""
import os
import pathlib
import sys
from urllib.parse import parse_qs, urlencode

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi import Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from main import app as _app  # noqa: E402

_PATH_PARAM = "__path"


class RestoreOriginalPath:
    """Undo a host rewrite so FastAPI sees the caller's real path."""

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


@_app.api_route(
    "/{unmatched:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
async def _unmatched(request: Request, unmatched: str):
    """Report what reached the function. Contains no secrets."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "no route matched",
            "received_path": request.url.path,
            "query_string": str(request.url.query),
            "root_path": request.scope.get("root_path", ""),
            "method": request.method,
            "known_routes": sorted(
                {r.path for r in _app.routes if getattr(r, "path", "").startswith(("/api", "/v1"))}
            ),
            "vercel_headers": {
                k: v for k, v in request.headers.items() if k.lower().startswith("x-vercel")
            },
            "env_present": {
                "ANTHROPIC_API_KEY": bool(os.getenv("ANTHROPIC_API_KEY")),
                "DATABASE_URL": bool(os.getenv("DATABASE_URL")),
                "ANTHROPIC_EFFORT": os.getenv("ANTHROPIC_EFFORT"),
            },
        },
    )


app = RestoreOriginalPath(_app)
