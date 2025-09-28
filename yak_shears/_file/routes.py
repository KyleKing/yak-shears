"""File routes for the Yak Shears application."""

from starlette.routing import Route

from .handlers import edit_yak_handler, yaks_handler

ROUTES = [
    Route("/files", endpoint=yaks_handler),
    Route("/edit", endpoint=edit_yak_handler, methods=["GET", "POST"]),
]
