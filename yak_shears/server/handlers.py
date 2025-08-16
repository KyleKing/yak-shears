"""Request handlers for the Yak Shears server."""

from http import HTTPStatus

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from yak_shears.constants import DEFAULT_REDIRECT
from yak_shears.templates import render_error


async def not_found(request: Request, exc: Exception) -> HTMLResponse:  # noqa: ARG001,RUF029
    """Handle 404 errors with a custom page.

    Args:
        request: The incoming request
        exc: The exception that occurred

    Returns:
        HTMLResponse with 404 message
    """
    return render_error("Not Found", status_code=HTTPStatus.NOT_FOUND)


async def favicon_handler(request: Request) -> Response:  # noqa: ARG001, RUF029
    """Handle favicon.ico requests to prevent 404 errors.

    Args:
        request: The incoming request

    Returns:
        Empty response with 204 No Content status
    """
    return Response(status_code=HTTPStatus.NO_CONTENT)


async def root_handler(request: Request) -> Response:  # noqa: ARG001, RUF029
    """Redirect root to home page.

    Args:
        request: The incoming request

    Returns:
        Redirect to home page
    """
    return RedirectResponse(url=DEFAULT_REDIRECT)
