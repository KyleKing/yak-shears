"""Authentication routes for Yak Shears."""

from starlette.routing import Route

from .handlers import login_handler, logout_handler, status_handler

ROUTES = [
    Route("/auth/login", endpoint=login_handler, methods=["GET", "POST"]),
    Route("/auth/logout", endpoint=logout_handler, methods=["GET"]),
    Route("/auth/status", endpoint=status_handler, methods=["GET"]),
]
PUBLIC_PATHS = {r"^/auth/[^/]{5,7}$"}
