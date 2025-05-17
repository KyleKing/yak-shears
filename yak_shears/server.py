"""Simple web server for Yak Shears using Python built-ins."""

import http.server
import socketserver
from urllib.parse import urlparse


class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom request handler that serves HTML responses for specific routes."""

    def do_GET(self):
        """Handle GET requests based on the requested path."""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/home':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<h1>hello world</h1>')
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<h1>404 Not Found</h1>')


def run_server(host='localhost', port=8000):
    """Run the HTTP server with the custom handler."""
    with socketserver.TCPServer((host, port), CustomHTTPRequestHandler) as httpd:
        print(f"Server running at http://{host}:{port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("Server stopped by user")


if __name__ == '__main__':
    run_server()