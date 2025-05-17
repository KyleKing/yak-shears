"""Server routes for Yak Shears."""

import os

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Route

from yak_shears import auth
from yak_shears.server.handlers import (
    echo_handler,
    edit_file_handler,
    files_handler,
    home_handler,
    root_handler,
    time_handler,
)


async def not_found(request: Request, exc: Exception) -> HTMLResponse:  # noqa: ARG001,RUF029
    """Handle 404 errors with a custom page.

    Args:
        request: The incoming request
        exc: The exception that occurred

    Returns:
        HTMLResponse with 404 message
    """
    return HTMLResponse("<h1>404 Not Found</h1>", status_code=404)


# Define routes for the application
routes = [
    Route("/", endpoint=root_handler),
    Route("/home", endpoint=home_handler),
    Route("/echo", endpoint=echo_handler, methods=["GET"]),
    Route("/echo", endpoint=echo_handler, methods=["POST"]),
    Route("/time", endpoint=time_handler),
    Route("/files", endpoint=files_handler),
    Route("/edit", endpoint=edit_file_handler, methods=["GET", "POST"]),
]

# Add auth routes
routes.extend(auth.auth_routes)


def start(host: str = "localhost", port: int = 8080) -> None:
    """Run the ASGI server with uvicorn.

    Args:
        host: The hostname to bind to
        port: The port to bind to
    """
    print(f"Server running at http://{host}:{port}")  # noqa: T201

    # Set WebAuthn environment variables
    os.environ.setdefault("WEBAUTHN_RP_ID", host)
    os.environ.setdefault("WEBAUTHN_ORIGIN", f"http://{host}:{port}")

    # Create app with auth middleware
    app = Starlette(
        routes=routes,
        debug=True,
        exception_handlers={404: not_found},
    )

    # Wrap app with auth middleware
    public_paths = ["/", "/home", "/auth/login", "/auth/register", "/auth/status"]
    app.add_middleware(auth.AuthMiddleware, public_paths=public_paths)

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start()
