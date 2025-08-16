"""Template rendering utilities."""

from http import HTTPStatus
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from starlette.responses import HTMLResponse

TEMPLATE_DIR = Path(__file__).parent

ENV = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=True,
)


def _render_template(template_name: str, *, status_code: HTTPStatus = HTTPStatus.OK, **context: Any) -> HTMLResponse:
    """Private render template by name.

    Args:
        template_name: The name of the template to render
        status_code: The HTTP status code to return
        **context: The context variables to pass to the template

    Returns:
        HTMLResponse with the rendered template
    """
    template = ENV.get_template(template_name)
    content = template.render(**context)
    return HTMLResponse(content, status_code=status_code)


def render_error(
    message: str,
    status_code: HTTPStatus = HTTPStatus.BAD_REQUEST,
) -> HTMLResponse:
    """Render an error page.

    Args:
        message: The error message to display
        status_code: The HTTP status code to return

    Returns:
        HTMLResponse with the error template
    """
    return _render_template("error.html.jinja", status_code=status_code, message=message)


def render_auth_login(redirect: str | None = None, error: str = "") -> HTMLResponse:
    """Render an error page.

    Args:
        error: optional error to display
        redirect: optional redirect path

    Returns:
        HTMLResponse with the error template
    """
    status_code = HTTPStatus.BAD_REQUEST if error else HTTPStatus.OK
    return _render_template("auth/login.html.jinja", redirect=redirect, error=error, status_code=status_code)
