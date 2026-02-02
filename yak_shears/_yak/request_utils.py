"""Request utilities for extracting and validating request data."""

from starlette.requests import Request


async def extract_yak_path(request: Request) -> str:
    """Extract yak path from request (handles both HTMX form and query params).

    For HTMX requests with form data, extracts from form data.
    For regular requests (GET or POST without HTMX), tries query params first,
    then falls back to form data.

    Returns:
        The yak path string (may be empty if not provided)
    """
    if is_htmx_request(request):
        form_data = await request.form()
        return str(form_data.get("yak", ""))

    yak_path = request.query_params.get("yak") or ""
    if not yak_path and request.method == "POST":
        form_data = await request.form()
        yak_path = str(form_data.get("yak", ""))
    return yak_path


def is_htmx_request(request: Request) -> bool:
    """Check if request is an HTMX request."""
    return request.headers.get("HX-Request") == "true"
