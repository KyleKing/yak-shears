"""Minimal Web Server using Starlette."""

import json
from datetime import datetime

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Route


async def home_handler(request: Request) -> HTMLResponse:
    """Handle requests to /home.

    Args:
        request: The incoming request

    Returns:
        HTMLResponse with hello world message
    """
    return HTMLResponse('<h1>hello world</h1>')


async def echo_handler(request: Request) -> HTMLResponse:
    """Handle both GET and POST requests to /echo.

    Args:
        request: The incoming request

    Returns:
        HTMLResponse with echoed data
    """
    # Build HTML response
    response = '<h1>Echo</h1>'

    # Add URL parameters to response if they exist
    query_params = dict(request.query_params)
    if query_params:
        response += '<h2>URL Parameters</h2>'
        response += '<ul>'
        for key, value in query_params.items():
            response += f"<li><strong>{key}</strong>: {value}</li>"
        response += '</ul>'

    # Add JSON data for POST requests
    if request.method == 'POST':
        try:
            json_data = await request.json()
            response += '<h2>JSON Payload</h2>'
            response += f"<pre>{json.dumps(json_data, indent=2)}</pre>"
        except json.JSONDecodeError:
            # Handle case where body is not valid JSON
            body = await request.body()
            if body:
                response += '<h2>Raw POST Data</h2>'
                response += f"<pre>{body.decode('utf-8')}</pre>"

    return HTMLResponse(response)


async def time_handler(request: Request) -> HTMLResponse:
    """Handle requests to /time.

    Args:
        request: The incoming request

    Returns:
        HTMLResponse with current time
    """
    now = datetime.now()
    return HTMLResponse(f"<h1>Current Time</h1><p>{now.strftime('%Y-%m-%d %H:%M:%S')}</p>")


async def not_found(request: Request, exc: Exception) -> HTMLResponse:
    """Handle 404 errors with a custom page.

    Args:
        request: The incoming request
        exc: The exception that occurred

    Returns:
        HTMLResponse with 404 message
    """
    return HTMLResponse('<h1>404 Not Found</h1>', status_code=404)


# Define routes for the application
routes = [
    Route('/home', endpoint=home_handler),
    Route('/echo', endpoint=echo_handler, methods=['GET']),
    Route('/echo', endpoint=echo_handler, methods=['POST']),
    Route('/time', endpoint=time_handler),
]


def run_server(host: str = 'localhost', port: int = 8000) -> None:
    """Run the ASGI server with Uvicorn.

    Args:
        host: The hostname to bind to
        port: The port to bind to
    """
    print(f"Server running at http://{host}:{port}")
    app = Starlette(
        routes=routes,
        debug=True,
        exception_handlers={404: not_found},
    )
    uvicorn.run(app, host=host, port=port)


if __name__ == '__main__':
    run_server()
