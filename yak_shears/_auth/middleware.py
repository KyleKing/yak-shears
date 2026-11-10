"""Authentication middleware for Starlette applications."""

import re
from http import HTTPStatus
from urllib.parse import quote, urlsplit
from warnings import catch_warnings, filterwarnings

from beartype.roar import BeartypeDecorHintPep585DeprecationWarning
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, RedirectResponse, Response

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
                response = await call_next(request)
                # Pages behind auth must not come back from the back-forward or HTTP
                # cache after the session ends, which would show notes without a login.
                response.headers.setdefault("Cache-Control", "no-store")
                return response
            login_url = f"/auth/login?redirect={quote(_return_path(request), safe='/')}"
            if request.headers.get("HX-Request"):
                # Following a redirect inside an XHR would hand the login page to the
                # caller as if it were the response. HX-Redirect makes htmx navigate.
                return PlainTextResponse(
                    "Session expired", status_code=HTTPStatus.UNAUTHORIZED, headers={"HX-Redirect": login_url}
                )
            return RedirectResponse(url=login_url, status_code=HTTPStatus.SEE_OTHER)

    def _return_path(request: Request) -> str:
        """Where to send the reader once they log back in.

        A background htmx request (a save, a search) is not where the reader was, so
        it returns them to the page that sent it. The query string is kept, because
        for the editor it is the only thing naming the open note.

        Returns:
            A same-origin path with its query string.
        """
        url = request.url
        if request.headers.get("HX-Request") and not request.headers.get("HX-Boosted"):
            current = urlsplit(request.headers.get("HX-Current-URL", ""))
            if current.netloc == url.netloc and current.path.startswith("/"):
                return f"{current.path}?{current.query}" if current.query else current.path
        return f"{url.path}?{url.query}" if url.query else url.path
