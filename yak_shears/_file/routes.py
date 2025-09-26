"""File routes for the Yak Shears application."""

from starlette.routing import Route

from .handlers import edit_file_handler, files_handler

ROUTES = [
    Route("/files", endpoint=files_handler),
    Route("/edit", endpoint=edit_file_handler, methods=["GET", "POST"]),
]
