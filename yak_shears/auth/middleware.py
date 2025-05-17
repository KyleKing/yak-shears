"""Authentication middleware for Starlette applications."""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from yak_shears.auth.webauthn import get_user_from_session


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for handling authentication."""

    def __init__(self, app, public_paths: list[str]) -> None:
        """Initialize the middleware.

        Args:
            app: The ASGI application
            public_paths: A list of paths that don't require authentication
        """
        super().__init__(app)
        self.public_paths = public_paths

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process the request through the middleware.

        Args:
            request: The incoming request
            call_next: The next request handler in the chain

        Returns:
            Response: The response
        """
        # Allow public paths without authentication
        if request.url.path in self.public_paths:
            return await call_next(request)

        # Check for authenticated user
        user = get_user_from_session(request)
        if user:
            return await call_next(request)

        # Redirect to login for non-authenticated users
        return RedirectResponse(url="/auth/login", status_code=303)
