"""Yak routes for the Yak Shears application."""

from starlette.routing import Route

from .handlers import (
    delete_yak_handler,
    edit_yak_handler,
    new_yak_handler,
    search_handler,
    yak_preview_handler,
    yaks_handler,
)

ROUTES = [
    Route("/yaks", endpoint=yaks_handler),
    Route("/search", endpoint=search_handler),
    Route("/new", endpoint=new_yak_handler, methods=["GET", "POST"]),
    Route("/edit", endpoint=edit_yak_handler, methods=["GET", "POST"]),
    Route("/delete", endpoint=delete_yak_handler, methods=["POST"]),
    Route("/api/yak-preview", endpoint=yak_preview_handler),
]
