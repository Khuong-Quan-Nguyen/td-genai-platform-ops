"""Vercel serverless entrypoint.

Vercel's Python runtime looks for a module-level ASGI app named `app`.

Path handling: a Vercel rewrite replaces the request path with the function's
own path, so FastAPI would see `/api/index` for every request and match
nothing. `vercel.json` therefore forwards the real path as a `__path` query
parameter, and the middleware below puts it back into the ASGI scope before
FastAPI routes the request. Any other query parameters the caller sent are
preserved.
"""
import pathlib
import sys
from urllib.parse import parse_qs, urlencode

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

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


app = RestoreOriginalPath(_app)
