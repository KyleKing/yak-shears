"""Authentication routes for the Yak Shears application."""

from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from os import getenv
from urllib.parse import urlparse

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from yak_shears._constants import DEFAULT_REDIRECT
from yak_shears._templates import render_auth_login

from . import storage
from .models import Password, SessionId, User

IN_TLS_CONTEXT = (getenv("IN_TLS_CONTEXT") or "").upper() == "TRUE"


def _validate_redirect_path(redirect_path: str) -> str:
    """Validate redirect path to prevent open redirect vulnerabilities.

    Args:
        redirect_path: The redirect path to validate

    Returns:
        str: Validated internal path or DEFAULT_REDIRECT if invalid
    """
    parsed = urlparse(redirect_path)
    if parsed.scheme or parsed.netloc or not redirect_path.startswith("/"):
        return DEFAULT_REDIRECT
    return redirect_path


async def login_handler(request: Request) -> Response:
    """Handle login requests.

    Args:
        request: The incoming request

    Returns:
        Response: HTML page for login or a redirect
    """
    if request.method == "GET":
        if user := get_user_from_session(request):
            return RedirectResponse(url=DEFAULT_REDIRECT)
        redirect_path = request.query_params.get("redirect")
        return render_auth_login(redirect=redirect_path)

    if request.method == "POST":
        form_data = await request.form()
        email = str(form_data.get("email", "")).strip()
        # Allow trailing spaces
        password = Password(str(form_data.get("password", "")).rstrip("\n"))
        redirect_path = _validate_redirect_path(str(form_data.get("redirect") or DEFAULT_REDIRECT).rstrip())
        if not email or not password:
            return render_auth_login(
                redirect=redirect_path,
                error="Email and password are required",
            )
        if not (user := await storage.authenticate_user(email, password)):
            return render_auth_login(
                redirect=redirect_path,
                error="Invalid email or password",
            )
        response = RedirectResponse(url=redirect_path, status_code=HTTPStatus.SEE_OTHER)
        session_id = storage.create_session(SessionId(user["id"]))
        expires = datetime.now(tz=UTC) + timedelta(weeks=1)
        response.set_cookie(
            "session_id",
            session_id,
            expires=expires.strftime("%a, %d-%b-%Y %H:%M:%S Z"),
            httponly=True,
            secure=IN_TLS_CONTEXT,
            samesite="strict",
            # PLANNED: specify the domain
        )
        return response

    error = f"Unsupported method {request.method}"
    raise NotImplementedError(error)


async def logout_handler(request: Request) -> Response:  # noqa: RUF029
    """Handle logout requests.

    Args:
        request: The incoming request

    Returns:
        Response: Redirect to home page
    """
    session_id = request.cookies.get("session_id")
    if session_id:
        storage.delete_session(session_id)

    response = RedirectResponse(url="/auth/login")
    response.delete_cookie("session_id")
    return response


async def status_handler(request: Request) -> JSONResponse:  # noqa: RUF029
    """Handle auth status requests.

    Args:
        request: The incoming request

    Returns:
        JSONResponse: Authentication status
    """
    if user := get_user_from_session(request):
        return JSONResponse({"authenticated": True, "email": user["email"], "displayName": user["display_name"]})
    return JSONResponse({"authenticated": False})


def get_user_from_session(request: Request) -> User | None:
    """Get user from session cookie.

    Args:
        request: The incoming request

    Returns:
        User | None: The authenticated user or None
    """
    if (session_id := request.cookies.get("session_id")) and (user_id := storage.get_user_id_from_session(session_id)):
        return storage.get_user_by_id(user_id)
    return None
