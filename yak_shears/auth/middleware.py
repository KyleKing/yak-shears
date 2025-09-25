"""Authentication middleware for Starlette applications."""

import re
from warnings import catch_warnings, filterwarnings

from beartype.roar import BeartypeDecorHintPep585DeprecationWarning
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from . import handlers  # for test mocking

# Ignore deprecation warnings only from specific starlette types
# https://beartype.readthedocs.io/en/latest/api_roar/#pep-585-deprecations
with catch_warnings():
    filterwarnings("ignore", category=BeartypeDecorHintPep585DeprecationWarning)

    from starlette.middleware.base import RequestResponseEndpoint
    from starlette.types import ASGIApp

    class AuthMiddleware(BaseHTTPMiddleware):
        """Middleware for handling authentication."""

        def __init__(self, app: ASGIApp, public_paths: set[str]) -> None:
            """Initialize the middleware.

            Args:
                app: The ASGI application
                public_paths: Paths that do not require authentication specified with regular expressions
            """
            super().__init__(app)
            if any(not pth.startswith("^") for pth in public_paths):
                msg = f"Public paths must be regular expressions and start with '^'. Found: {public_paths}"
                raise ValueError(msg)
            self.public_path_matchers = {re.compile(pth) for pth in public_paths}

        async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
            """Process the request through the middleware.

            Args:
                request: The incoming request
                call_next: The next request handler in the chain

            Returns:
                Response: The response
            """
            if any(pth.match(request.url.path) for pth in self.public_path_matchers):
                return await call_next(request)
            if handlers.get_user_from_session(request):
                return await call_next(request)
            return RedirectResponse(url=f"/auth/login?redirect={request.url.path}")
