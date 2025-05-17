"""Template rendering utilities for Yak Shears."""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from starlette.responses import HTMLResponse

# Get the parent directory of this file (yak_shears package directory)
package_dir = Path(__file__).parent
# Template directory is relative to the package directory
template_dir = package_dir / "templates"

# Create Jinja2 environment
env = Environment(
    loader=FileSystemLoader(str(template_dir)),
    autoescape=True,  # Important for security to escape HTML by default
)

# Add custom filters if needed
env.filters["tojson"] = lambda obj: env.jinja_options["extensions"][0].filter_json(obj)
env.add_extension("jinja2.ext.do")


def render_template(template_name: str, **context: Any) -> HTMLResponse:
    """Render a template and return an HTMLResponse.

    Args:
        template_name: The name of the template to render
        **context: The context variables to pass to the template

    Returns:
        HTMLResponse with the rendered template
    """
    template = env.get_template(template_name)
    content = template.render(**context)
    return HTMLResponse(content)


def render_error(message: str, back_url: str = "/home", status_code: int = 400) -> HTMLResponse:
    """Render an error page.

    Args:
        message: The error message to display
        back_url: The URL to redirect back to
        status_code: The HTTP status code to return

    Returns:
        HTMLResponse with the error template
    """
    template = env.get_template("error.html.jinja")
    content = template.render(message=message, back_url=back_url)
    return HTMLResponse(content, status_code=status_code)
