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


def render_template(template_name: str, status_code: HTTPStatus = HTTPStatus.OK, **context: Any) -> HTMLResponse:
    """Render template by name.

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
        back_url: The URL to redirect back to
        status_code: The HTTP status code to return

    Returns:
        HTMLResponse with the error template
    """
    template = ENV.get_template("error.html.jinja")
    content = template.render(message=message)
    return HTMLResponse(content, status_code=status_code)
