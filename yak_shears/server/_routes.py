"""Server routes for Yak Shears."""

import argparse

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.staticfiles import StaticFiles

from yak_shears._auth.middleware import AuthMiddleware
from yak_shears._auth.routes import PUBLIC_PATHS as AUTH_PUBLIC_PATHS
from yak_shears._auth.routes import ROUTES as AUTH_ROUTES
from yak_shears._file.routes import ROUTES as FILE_ROUTES
from yak_shears._log_utils import log

from ._handlers import favicon_handler, not_found, root_handler

ROUTES = [
    Route("/", endpoint=root_handler),
    Route("/favicon.ico", endpoint=favicon_handler),
    *FILE_ROUTES,
    *AUTH_ROUTES,
]


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
    app.mount("/static", StaticFiles(directory="yak_shears/static"), name="static")
    return app


def create_app() -> Starlette:  # pragma: no cover
    """Create and configure the Starlette application.

    Returns:
        Starlette: The configured Starlette application
    """
    app = create_app_without_auth()

    public_paths = {r"^/$", r"^/favicon.ico$", r"^/static/.+", *AUTH_PUBLIC_PATHS}
    app.add_middleware(AuthMiddleware, public_paths=public_paths)

    return app


def start(
    host: str = "localhost",
    port: int = 8080,
    *,
    reload: bool = False,
    no_auth: bool = True,
) -> None:  # pragma: no cover
    """Run the ASGI server with uvicorn.

    Args:
        host: The hostname to bind to
        port: The port to bind to
        reload: Whether to reload the server on code changes
        no_auth: Turn off auth middleware. Only use for local development and only allowed when reload is also specified
    """
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
        uvicorn.run(create_app(), host=host, port=port)


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

    args = parser.parse_args()

    start(host=args.host, port=args.port, reload=args.reload, no_auth=args.no_auth)
