from http import HTTPStatus

import pytest
from bs4 import BeautifulSoup
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route
from starlette.testclient import TestClient
from syrupy.assertion import SnapshotAssertion

from yak_shears.auth.middleware import AuthMiddleware
from yak_shears.auth.routes import PUBLIC_PATHS as AUTH_PUBLIC_PATHS
from yak_shears.auth.routes import ROUTES as AUTH_ROUTES
from yak_shears.constants import DEFAULT_REDIRECT

from .conftest import SAMPLE_USER_EMAIL, SAMPLE_USER_PASSWORD


@pytest.fixture
def auth_app(temp_user_file) -> Starlette:
    """Create a test Starlette application with authentication.

    Returns:
        Starlette: A test Starlette application
    """
    app = Starlette(routes=AUTH_ROUTES, debug=True)
    app.add_middleware(AuthMiddleware, public_paths=AUTH_PUBLIC_PATHS)
    return app


@pytest.fixture
def auth_client(auth_app: Starlette) -> TestClient:
    """Create a TestClient for the Starlette application.

    Args:
        auth_app: The Starlette application

    Returns:
        TestClient: A test client for the application
    """
    return TestClient(auth_app, follow_redirects=False)


def post_login(client: TestClient) -> None:
    """Create a TestClient for the Starlette application.

    Args:
        client: TestClient
    """
    login_response = client.post(
        "/auth/login",
        data={"email": SAMPLE_USER_EMAIL, "password": SAMPLE_USER_PASSWORD},
    )

    assert login_response.status_code == HTTPStatus.SEE_OTHER


@pytest.mark.parametrize(
    ("email", "password", "expected_content"),
    [
        (SAMPLE_USER_EMAIL, "wrong_password", b"Invalid email or password"),
        ("nonexistent@example.com", "password", b"Invalid email or password"),
        (SAMPLE_USER_EMAIL + " ", SAMPLE_USER_PASSWORD + " ", b"Invalid email or password"),
        (None, "password", b"Email and password are required"),
        (SAMPLE_USER_EMAIL, None, b"Email and password are required"),
        ("", "password", b"Email and password are required"),
        (SAMPLE_USER_EMAIL, "", b"Email and password are required"),
    ],
    ids=[
        "Invalid Password",
        "Non-existent user",
        "Trailing spaces are preserved",
        "Missing Email",
        "Missing Password",
        "Empty Email",
        "Empty Password",
    ],
)
def test_login_errors(auth_client, sample_user, email, password, expected_content):
    """Test login POST requests with various input errors."""
    response = auth_client.post("/auth/login", data={"email": email, "password": password})

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert expected_content in response.content


def test_displayed_error(auth_client, snapshot: SnapshotAssertion):
    """Test that the error message is displayed in the login form."""
    expected_content = b"Invalid email or password"

    response = auth_client.post("/auth/login", data={"email": "...", "password": "..."})

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert expected_content in response.content
    assert BeautifulSoup(response.content.decode("utf-8"), "html.parser").prettify() == snapshot()


def test_login_get_shows_form(auth_client, snapshot: SnapshotAssertion):
    """Test that GET /auth/login shows the login form."""
    response = auth_client.get("/auth/login")

    assert response.status_code == HTTPStatus.OK
    assert BeautifulSoup(response.content.decode("utf-8"), "html.parser").prettify() == snapshot()


def test_login_handles_newlines_in_input(auth_client, sample_user):
    """Test that login handles newlines in email/password input."""
    response = auth_client.post(
        "/auth/login",
        # Should still work (newlines should be stripped)
        data={"email": SAMPLE_USER_EMAIL + "\n", "password": SAMPLE_USER_PASSWORD + "\n"},
    )

    assert response.status_code == HTTPStatus.SEE_OTHER
    assert response.headers["location"] == DEFAULT_REDIRECT


def test_login_keeps_redirect(auth_client, sample_user):
    """Test that login keeps the redirect."""
    response = auth_client.post(
        "/auth/login",
        data={"email": SAMPLE_USER_EMAIL, "password": SAMPLE_USER_PASSWORD, "redirect": "/page/abc"},
    )

    assert response.status_code == HTTPStatus.SEE_OTHER
    assert response.headers["location"] == "/page/abc"


@pytest.mark.parametrize(
    ("is_logged_in",),
    [
        (True,),
        (False,),
    ],
)
def test_logout(auth_client, sample_user, is_logged_in):
    """Test GET /auth/logout in logged in and logged out states."""
    if is_logged_in:
        post_login(auth_client)

    response = auth_client.get("/auth/logout")

    assert response.status_code == HTTPStatus.TEMPORARY_REDIRECT
    assert response.headers["location"] == "/auth/login"

    if is_logged_in:
        session_cookies = [cookie for cookie in response.cookies if cookie.name == "session_id"]
        assert len(session_cookies) == 0, "Expected session cookie to be deleted"


@pytest.mark.parametrize(
    ("setup_func", "expected_authenticated", "expected_email"),
    [
        (lambda client: None, False, None),
        (lambda client: post_login(client), True, SAMPLE_USER_EMAIL),
        (lambda client: client.cookies.set("session_id", "invalid-session-id"), False, None),
    ],
)
def test_auth_status(auth_client, sample_user, setup_func, expected_authenticated, expected_email):
    """Test /auth/status in various authentication states."""
    setup_func(auth_client)

    status_response = auth_client.get("/auth/status")

    assert status_response.status_code == HTTPStatus.OK
    assert status_response.headers["content-type"] == "application/json"
    data = status_response.json()
    assert data["authenticated"] == expected_authenticated
    if expected_email:
        assert data["email"] == expected_email


def create_middleware_app(temp_user_file, sample_user, protected_route=False):
    """Helper to create app with middleware for testing."""
    routes = AUTH_ROUTES
    if protected_route:

        async def protected_endpoint(request):
            return Response("Protected content")

        routes = [Route("/protected", endpoint=protected_endpoint), *routes]

    app = Starlette(routes=routes)
    app.add_middleware(AuthMiddleware, public_paths=AUTH_PUBLIC_PATHS)
    return TestClient(app, follow_redirects=False)


@pytest.mark.parametrize(
    ("is_authenticated", "endpoint", "expected_status", "expected_location"),
    [
        (False, "/auth/login", HTTPStatus.OK, None),
        (False, "/protected", HTTPStatus.TEMPORARY_REDIRECT, "/auth/login?redirect=http://testserver/protected"),
        (True, "/protected", HTTPStatus.OK, None),
    ],
)
def test_middleware_behavior(
    temp_user_file, sample_user, is_authenticated, endpoint, expected_status, expected_location
):
    """Test middleware allows public paths and protects others."""
    client = create_middleware_app(temp_user_file, sample_user, protected_route=True)

    if is_authenticated:
        post_login(client)

    response = client.get(endpoint)
    assert response.status_code == expected_status

    if expected_location:
        assert response.headers["location"] == expected_location
    elif is_authenticated and endpoint == "/protected":
        assert b"Protected content" in response.content
