"""File routes for the Yak Shears application."""

from starlette.routing import Route

from .handlers import edit_file_handler, yaks_handler

ROUTES = [
    Route("/files", endpoint=yaks_handler),
    Route("/edit", endpoint=edit_file_handler, methods=["GET", "POST"]),
]
