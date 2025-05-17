"""Simple web server for Yak Shears using Python built-ins."""

import http.server
import json
import socketserver
from typing import Any, Callable, Dict, Optional
from urllib.parse import parse_qs, urlparse


# Type alias for request handlers
RequestHandler = Callable[['Router', Dict[str, Any]], str]


class Router:
    """Router class that manages endpoints and their handler functions."""

    def __init__(self):
        """Initialize the router with empty route dictionaries."""
        self.get_routes: Dict[str, RequestHandler] = {}
        self.post_routes: Dict[str, RequestHandler] = {}

        # Register built-in routes
        self.register_route('GET', '/home', home_handler)
        self.register_route('GET', '/echo', echo_get_handler)
        self.register_route('POST', '/echo', echo_post_handler)

    def register_route(self, method: str, path: str, handler: RequestHandler) -> None:
        """Register a route with the router.

        Args:
            method: HTTP method ('GET', 'POST', etc.)
            path: URL path for the route
            handler: Function that handles the request
        """
        if method == 'GET':
            self.get_routes[path] = handler
        elif method == 'POST':
            self.post_routes[path] = handler
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

    def handle_request(self, server_handler: 'CustomHTTPRequestHandler', method: str) -> bool:
        """Handle an incoming HTTP request.

        Args:
            server_handler: The HTTP request handler instance
            method: HTTP method for this request

        Returns:
            True if the request was handled, False if no matching route was found
        """
        parsed_path = urlparse(server_handler.path)
        path = parsed_path.path

        # Select routes based on the HTTP method
        routes = self.get_routes if method == 'GET' else self.post_routes

        if path in routes:
            # Prepare request context
            request_context = {
                'path': path,
                'query_params': parse_qs(parsed_path.query),
                'headers': server_handler.headers,
            }

            # For POST requests, add body data
            if method == 'POST':
                content_length = int(server_handler.headers.get('Content-Length', 0))
                post_data = server_handler.rfile.read(content_length)
                request_context['post_data'] = post_data

                # Try to parse as JSON if appropriate
                content_type = server_handler.headers.get('Content-Type', '')
                if 'application/json' in content_type and content_length > 0:
                    try:
                        request_context['json_data'] = json.loads(post_data.decode('utf-8'))
                    except json.JSONDecodeError:
                        request_context['json_data'] = {'error': 'Invalid JSON payload'}

            # Call the handler for this route
            response_html = routes[path](self, request_context)

            # Send the response
            server_handler.send_response(200)
            server_handler.send_header('Content-type', 'text/html')
            server_handler.end_headers()
            server_handler.wfile.write(response_html.encode('utf-8'))
            return True

        return False


# Built-in route handlers
def home_handler(router: Router, request: Dict[str, Any]) -> str:
    """Handle requests to /home."""
    return '<h1>hello world</h1>'


def echo_get_handler(router: Router, request: Dict[str, Any]) -> str:
    """Handle GET requests to /echo."""
    query_params = request.get('query_params', {})

    # Build HTML response
    response = '<h1>Echo</h1>'
    if query_params:
        response += '<h2>URL Parameters</h2>'
        response += '<ul>'
        for key, values in query_params.items():
            for value in values:
                response += f"<li><strong>{key}</strong>: {value}</li>"
        response += '</ul>'

    return response


def echo_post_handler(router: Router, request: Dict[str, Any]) -> str:
    """Handle POST requests to /echo."""
    query_params = request.get('query_params', {})
    json_data = request.get('json_data', {})

    # Build HTML response
    response = '<h1>Echo</h1>'

    # Add URL parameters to response if they exist
    if query_params:
        response += '<h2>URL Parameters</h2>'
        response += '<ul>'
        for key, values in query_params.items():
            for value in values:
                response += f"<li><strong>{key}</strong>: {value}</li>"
        response += '</ul>'

    # Add JSON data to response if it exists
    if json_data:
        response += '<h2>JSON Payload</h2>'
        response += '<pre>' + json.dumps(json_data, indent=2) + '</pre>'

    return response


class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom request handler that uses a router to handle requests."""

    # Create a router instance to be shared across all request handler instances
    router = Router()

    def do_GET(self):
        """Handle GET requests by delegating to the router."""
        if not self.router.handle_request(self, 'GET'):
            self.send_error_response(404)

    def do_POST(self):
        """Handle POST requests by delegating to the router."""
        if not self.router.handle_request(self, 'POST'):
            self.send_error_response(404)

    def send_error_response(self, status_code: int, message: Optional[str] = None):
        """Send an error response with the given status code and message."""
        self.send_response(status_code)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        if status_code == 404:
            self.wfile.write(b'<h1>404 Not Found</h1>')
        else:
            error_message = message or f"Error {status_code}"
            self.wfile.write(f"<h1>{error_message}</h1>".encode('utf-8'))


def run_server(host='localhost', port=8000):
    """Run the HTTP server with the custom handler."""
    with socketserver.TCPServer((host, port), CustomHTTPRequestHandler) as httpd:
        print(f"Server running at http://{host}:{port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('Server stopped by user')


# Example of how to add a new route
def add_custom_route():
    """Add a custom route to the router."""

    def time_handler(router: Router, request):
        """Example handler that returns the current time."""
        from datetime import datetime

        now = datetime.now()
        return f"<h1>Current Time</h1><p>{now.strftime('%Y-%m-%d %H:%M:%S')}</p>"

    # Register the route with the router
    CustomHTTPRequestHandler.router.register_route('GET', '/time', time_handler)


# Add example custom route
add_custom_route()


if __name__ == '__main__':
    run_server()
