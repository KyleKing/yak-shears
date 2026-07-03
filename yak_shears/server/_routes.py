"""Server routes for Yak Shears."""

import argparse
import os

import uvicorn
from starlette.applications import Starlette
from starlette.datastructures import MutableHeaders
from starlette.responses import Response
from starlette.routing import Route
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from yak_shears._auth.middleware import AuthMiddleware
from yak_shears._auth.routes import PUBLIC_PATHS as AUTH_PUBLIC_PATHS
from yak_shears._auth.routes import ROUTES as AUTH_ROUTES
from yak_shears._log_utils import log
from yak_shears._yak.routes import ROUTES as YAK_ROUTES

from ._handlers import favicon_handler, not_found, root_handler

_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data:; "
    "frame-ancestors 'none'"
)

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}

ROUTES = [
    Route("/", endpoint=root_handler),
    Route("/favicon.ico", endpoint=favicon_handler),
    *YAK_ROUTES,
    *AUTH_ROUTES,
]


class SecurityHeadersMiddleware:
    """Attach baseline security response headers to every HTTP response."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "same-origin"
                headers["Content-Security-Policy"] = _CONTENT_SECURITY_POLICY
            await send(message)

        await self._app(scope, receive, send_with_headers)


class RevalidateStaticFiles(StaticFiles):
    """Static files that must be revalidated so edits are picked up immediately.

    Responses keep their ETag/Last-Modified for cheap 304s, but `no-cache`
    forces the browser to revalidate rather than serve a stale cached asset.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


def create_app_without_auth() -> Starlette:  # pragma: no cover
    """Only used for local development and testing.

    Returns:
        Starlette: The configured Starlette application
    """
    app = Starlette(
        routes=ROUTES,
        debug=True,
        exception_handlers={404: not_found},
    )
    app.mount("/static", RevalidateStaticFiles(directory="yak_shears/static"), name="static")
    return app


def create_app() -> Starlette:  # pragma: no cover
    """Create and configure the Starlette application.

    Returns:
        Starlette: The configured Starlette application
    """
    app = create_app_without_auth()

    public_paths = {r"^/$", r"^/favicon.ico$", r"^/static/.+", *AUTH_PUBLIC_PATHS}
    app.add_middleware(AuthMiddleware, public_paths=public_paths)
    app.add_middleware(SecurityHeadersMiddleware)

    return app


def start(
    host: str = "localhost",
    port: int = 8080,
    *,
    reload: bool = False,
    no_auth: bool = True,
    search_db_dir: str | None = None,
) -> None:  # pragma: no cover
    """Run the ASGI server with uvicorn.

    Args:
        host: The hostname to bind to
        port: The port to bind to
        reload: Whether to reload the server on code changes
        no_auth: Turn off auth middleware. Only use for local development and only allowed when reload is also specified
        search_db_dir: Directory for the search database

    Raises:
        ValueError: If no_auth is requested without reload, or with a non-loopback host.
    """
    if no_auth and not reload:
        raise ValueError("--no-auth is only permitted together with --reload for local development")
    if no_auth and host not in _LOOPBACK_HOSTS:
        msg = f"--no-auth refuses to bind to non-loopback host {host!r}"
        raise ValueError(msg)

    if search_db_dir:
        os.environ["SEARCH_DB_DIR"] = search_db_dir

    log(f"Server running at http://{host}:{port}")

    if reload:
        log("Auto-reload enabled: Server will restart on code changes")
        uvicorn.run(
            "yak_shears.server._routes:create_app_without_auth" if no_auth else "yak_shears.server._routes:create_app",
            host=host,
            port=port,
            reload=True,
            reload_dirs=["yak_shears"],
        )
    else:
        app = create_app_without_auth() if no_auth else create_app()
        uvicorn.run(app, host=host, port=port)


def cli() -> None:
    """Run the development server with auto-reload."""
    parser = argparse.ArgumentParser(description="Run the Yak Shears development server")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Utilize auto-reload")
    parser.add_argument(
        "--no-auth",
        action="store_true",
        help="Turn off auth middleware. Only use for local development and only allowed when reload is also specified",
    )
    parser.add_argument(
        "--search-db-dir",
        help="Directory for the search database",
    )

    args = parser.parse_args()

    start(host=args.host, port=args.port, reload=args.reload, no_auth=args.no_auth, search_db_dir=args.search_db_dir)
