"""Yak routes for the Yak Shears application."""

from starlette.routing import Route

from .handlers import edit_yak_handler, new_yak_handler, yaks_handler

ROUTES = [
    Route("/yaks", endpoint=yaks_handler),
    Route("/new", endpoint=new_yak_handler, methods=["GET", "POST"]),
    Route("/edit", endpoint=edit_yak_handler, methods=["GET", "POST"]),
]
