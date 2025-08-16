"""Authentication routes for the Yak Shears application."""

from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from os import getenv

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.routing import Route

from yak_shears.templates import render_template

from . import storage
from .models import Password, SessionId, User

IN_TLS_CONTEXT = (getenv("IN_TLS_CONTEXT") or "").upper() == "TRUE"
DEFAULT_REDIRECT = "/files"


async def login_handler(request: Request) -> Response:
    """Handle login requests.

    Args:
        request: The incoming request

    Returns:
        Response: HTML page for login or a redirect
    """
    if request.method == "GET":
        if user := get_user_from_session(request):
            return RedirectResponse(url="/home")
        redirect_path = request.query_params.get("redirect")
        return render_template("auth/login.html.jinja", redirect=redirect_path)

    if request.method == "POST":
        form_data = await request.form()
        email = str(form_data.get("email", "")).strip()
        # Allow trailing spaces
        password = Password(str(form_data.get("password", "")).rstrip("\n"))
        if not email or not password:
            return render_template(
                "auth/login.html.jinja",
                HTTPStatus.BAD_REQUEST,
                error="Email and password are required",
                redirect=form_data.get("redirect"),
            )
        if not (user := storage.authenticate_user(email, password)):
            return render_template(
                "auth/login.html.jinja",
                HTTPStatus.BAD_REQUEST,
                error="Invalid email or password",
                redirect=form_data.get("redirect"),
            )
        redirect_path = str(form_data.get("redirect") or DEFAULT_REDIRECT).rstrip()
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

    response = RedirectResponse(url="/home")
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


ROUTES = [
    Route("/auth/login", endpoint=login_handler, methods=["GET", "POST"]),
    Route("/auth/logout", endpoint=logout_handler, methods=["GET"]),
    Route("/auth/status", endpoint=status_handler, methods=["GET"]),
]
PUBLIC_PATHS = {"/auth/login", "/auth/logout", "/auth/status"}
