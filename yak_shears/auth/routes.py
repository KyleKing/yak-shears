"""Authentication routes for the Yak Shears application."""

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.routing import Route

from yak_shears.templates import render_template

from . import storage
from .models import Password, SessionId


async def login_handler(request: Request) -> Response:
    """Handle login requests.

    Args:
        request: The incoming request

    Returns:
        Response: HTML page for login or a redirect
    """
    if request.method == "GET":
        if not (user := get_user_from_session(request)):
            return RedirectResponse(url="/home")
        return render_template("auth/login.html.jinja")

    if request.method == "POST":
        form_data = await request.form()
        email = str(form_data.get("email", "")).rstrip("\n")
        password = Password(str(form_data.get("password", "")).rstrip("\n"))
        if not email or not password:
            return render_template("auth/login.html.jinja", error="Email and password are required")
        if not (user := storage.authenticate_user(email, password)):
            return render_template("auth/login.html.jinja", error="Invalid email or password")
        session_id = storage.create_session(SessionId(user["id"]))
        response = RedirectResponse(url="/home")
        response.set_cookie("session_id", session_id, httponly=True, secure=False, samesite="lax")
        return response

    raise NotImplementedError(f"Unsupported method {request.method}")


async def logout_handler(request: Request) -> Response:
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


async def status_handler(request: Request) -> JSONResponse:
    """Handle auth status requests.

    Args:
        request: The incoming request

    Returns:
        JSONResponse: Authentication status
    """
    if user := get_user_from_session(request):
        return JSONResponse({"authenticated": True, "email": user["email"], "displayName": user["display_name"]})
    return JSONResponse({"authenticated": False})


def get_user_from_session(request: Request):
    """Get user from session cookie.

    Args:
        request: The incoming request

    Returns:
        User | None: The authenticated user or None
    """
    if session_id := request.cookies.get("session_id"):
        if user_id := storage.get_user_id_from_session(session_id):
            return storage.get_user_by_id(user_id)
    return None


ROUTES = [
    Route("/auth/login", endpoint=login_handler, methods=["GET", "POST"]),
    Route("/auth/logout", endpoint=logout_handler, methods=["GET", "POST"]),
    Route("/auth/status", endpoint=status_handler, methods=["GET"]),
]
