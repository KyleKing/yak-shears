"""Routes for the sync API a native client uses."""

from starlette.routing import Route

from .handlers import (
    manifest_handler,
    token_create_handler,
    token_delete_handler,
    yak_delete_handler,
    yak_get_handler,
    yak_put_handler,
)

ROUTES = [
    Route("/api/v1/token", endpoint=token_create_handler, methods=["POST"]),
    Route("/api/v1/token", endpoint=token_delete_handler, methods=["DELETE"]),
    Route("/api/v1/yaks", endpoint=manifest_handler, methods=["GET"]),
    Route("/api/v1/yaks/{path:path}", endpoint=yak_get_handler, methods=["GET"]),
    Route("/api/v1/yaks/{path:path}", endpoint=yak_put_handler, methods=["PUT"]),
    Route("/api/v1/yaks/{path:path}", endpoint=yak_delete_handler, methods=["DELETE"]),
]
# Trading credentials for a token has to happen before there is one. Revoking
# checks the bearer itself in the handler.
PUBLIC_PATHS = {r"^/api/v1/token$"}
