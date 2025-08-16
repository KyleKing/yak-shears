"""Server routes for Yak Shears."""

import argparse
from http import HTTPStatus

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Route

from yak_shears.auth.middleware import AuthMiddleware
from yak_shears.auth.routes import PUBLIC_PATHS as AUTH_PUBLIC_PATHS
from yak_shears.auth.routes import ROUTES as AUTH_ROUTES
from yak_shears.log_utils import log
from yak_shears.server.handlers import edit_file_handler, files_handler, root_handler


async def not_found(request: Request, exc: Exception) -> HTMLResponse:  # noqa: ARG001,RUF029
    """Handle 404 errors with a custom page.

    Args:
        request: The incoming request
        exc: The exception that occurred

    Returns:
        HTMLResponse with 404 message
    """
    return HTMLResponse("<h2>404 Not Found</h2>", status_code=HTTPStatus.NOT_FOUND)


ROUTES = [
    Route("/", endpoint=root_handler),
    Route("/files", endpoint=files_handler),
    Route("/edit", endpoint=edit_file_handler, methods=["GET", "POST"]),
    *AUTH_ROUTES,
]


def create_app() -> Starlette:
    """Create and configure the Starlette application.

    Returns:
        Starlette: The configured Starlette application
    """
    # Create app with auth middleware
    app = Starlette(
        routes=ROUTES,
        debug=True,
        exception_handlers={404: not_found},
    )

    # Wrap app with auth middleware
    public_paths = {"/", "/home", *AUTH_PUBLIC_PATHS}
    app.add_middleware(AuthMiddleware, public_paths=public_paths)

    return app


def start(host: str = "localhost", port: int = 8080, *, reload: bool = False) -> None:
    """Run the ASGI server with uvicorn.

    Args:
        host: The hostname to bind to
        port: The port to bind to
        reload: Whether to reload the server on code changes
    """
    log(f"Server running at http://{host}:{port}")

    if reload:
        log("Auto-reload enabled: Server will restart on code changes")
        uvicorn.run(
            "yak_shears.server.routes:create_app",
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

    args = parser.parse_args()

    start(host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    cli()
