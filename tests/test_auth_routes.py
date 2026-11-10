from http import HTTPStatus

import pytest
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route
from starlette.testclient import TestClient
from syrupy.assertion import SnapshotAssertion

from yak_shears._auth.middleware import AuthMiddleware
from yak_shears._auth.routes import PUBLIC_PATHS as AUTH_PUBLIC_PATHS
from yak_shears._auth.routes import ROUTES as AUTH_ROUTES
from yak_shears._constants import DEFAULT_REDIRECT

from .conftest import SAMPLE_USER_EMAIL, SAMPLE_USER_PASSWORD, stable_html


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
    assert stable_html(response.content) == snapshot()


def test_login_get_shows_form(auth_client, snapshot: SnapshotAssertion):
    """Test that GET /auth/login shows the login form."""
    response = auth_client.get("/auth/login")

    assert response.status_code == HTTPStatus.OK
    assert stable_html(response.content) == snapshot()


@pytest.mark.parametrize(
    ("redirect", "expected"),
    [
        (None, DEFAULT_REDIRECT),
        ("/edit?yak=a.dj", "/edit?yak=a.dj"),
        ("https://evil.example/", DEFAULT_REDIRECT),
    ],
    ids=["default", "same-origin", "foreign"],
)
def test_login_get_when_already_logged_in(auth_client, sample_user, redirect, expected):
    """A logged-in reader skips the form and goes where the redirect pointed, if it is safe."""
    post_login(auth_client)

    response = auth_client.get("/auth/login", params={"redirect": redirect} if redirect else None)

    assert response.status_code == HTTPStatus.TEMPORARY_REDIRECT
    assert response.headers["location"] == expected


def test_login_method_handling(auth_client):
    """An undeclared method is refused, and HEAD is answered like GET."""
    assert auth_client.request("PATCH", "/auth/login").status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert auth_client.head("/auth/login").status_code == HTTPStatus.OK


def test_login_handles_newlines_in_input(auth_client, sample_user):
    """Test that login handles newlines in email/password input."""
    response = auth_client.post(
        "/auth/login",
        # Should still work (newlines should be stripped)
        data={"email": SAMPLE_USER_EMAIL + "\n", "password": SAMPLE_USER_PASSWORD + "\n"},
    )

    assert response.status_code == HTTPStatus.SEE_OTHER
    assert response.headers["location"] == DEFAULT_REDIRECT


@pytest.mark.parametrize("redirect", ["/page/abc", "/edit?yak=cat/a.dj"])
def test_login_keeps_redirect(auth_client, sample_user, redirect):
    """Login returns to the redirect, query string included."""
    response = auth_client.post(
        "/auth/login",
        data={"email": SAMPLE_USER_EMAIL, "password": SAMPLE_USER_PASSWORD, "redirect": redirect},
    )

    assert response.status_code == HTTPStatus.SEE_OTHER
    assert response.headers["location"] == redirect


def test_logout_get(auth_client, sample_user):
    """Test GET /auth/logout."""
    post_login(auth_client)

    logout_response = auth_client.get("/auth/logout")

    assert logout_response.status_code == HTTPStatus.TEMPORARY_REDIRECT
    assert logout_response.headers["location"] == "/auth/login"
    session_cookies = [cookie for cookie in logout_response.cookies if cookie == "session_id"]
    assert len(session_cookies) == 0, "Expected session cookie to be deleted"


def test_logout_when_not_logged_in(auth_client):
    """Test logout when not logged in."""
    response = auth_client.get("/auth/logout")

    assert response.status_code == HTTPStatus.TEMPORARY_REDIRECT
    assert response.headers["location"] == "/auth/login"


def test_status_when_not_logged_in(auth_client):
    """Test /auth/status when not authenticated."""
    status_response = auth_client.get("/auth/status")

    assert status_response.status_code == HTTPStatus.OK
    assert status_response.headers["content-type"] == "application/json"
    assert status_response.json() == {"authenticated": False}


def test_status_when_logged_in(auth_client, sample_user):
    """Test /auth/status when authenticated."""
    post_login(auth_client)

    status_response = auth_client.get("/auth/status")

    assert status_response.status_code == HTTPStatus.OK
    assert status_response.headers["content-type"] == "application/json"
    data = status_response.json()
    assert data["authenticated"] is True
    assert data["email"] == SAMPLE_USER_EMAIL


def test_status_with_invalid_session(auth_client):
    """Test /auth/status with invalid session cookie."""
    auth_client.cookies.set("session_id", "invalid-session-id")

    status_response = auth_client.get("/auth/status")

    assert status_response.status_code == HTTPStatus.OK
    assert status_response.json() == {"authenticated": False}


def test_middleware_allows_public_paths(temp_user_file):
    """Test that middleware allows access to public paths."""
    app = Starlette(routes=AUTH_ROUTES)
    app.add_middleware(AuthMiddleware, public_paths=AUTH_PUBLIC_PATHS)

    client = TestClient(app, follow_redirects=False)

    # Should allow access to public paths even when not logged in
    response = client.get("/auth/login")
    assert response.status_code == HTTPStatus.OK
    status_response = client.get("/auth/status")
    assert status_response.status_code == HTTPStatus.OK
    assert status_response.json() == {"authenticated": False}


@pytest.mark.parametrize(
    ("method", "url", "headers", "status", "location_header", "login_url"),
    [
        ("GET", "/protected", {}, HTTPStatus.SEE_OTHER, "location", "/auth/login?redirect=/protected"),
        # The query names the open note, so dropping it loses the reader's place
        (
            "GET",
            "/protected?yak=cat/2026-07-22T14_03_51Z.dj&x=1",
            {},
            HTTPStatus.SEE_OTHER,
            "location",
            "/auth/login?redirect=/protected%3Fyak%3Dcat/2026-07-22T14_03_51Z.dj%26x%3D1",
        ),
        # A background save returns the reader to the page it came from, not the endpoint
        (
            "POST",
            "/protected",
            {"HX-Request": "true", "HX-Current-URL": "http://testserver/edit?yak=a.dj"},
            HTTPStatus.UNAUTHORIZED,
            "HX-Redirect",
            "/auth/login?redirect=/edit%3Fyak%3Da.dj",
        ),
        # Another origin in HX-Current-URL is ignored rather than followed
        (
            "POST",
            "/protected",
            {"HX-Request": "true", "HX-Current-URL": "https://evil.example/edit?yak=a.dj"},
            HTTPStatus.UNAUTHORIZED,
            "HX-Redirect",
            "/auth/login?redirect=/protected",
        ),
        # A boosted link is a navigation, so the target is where the reader was going
        (
            "GET",
            "/protected?page=2",
            {"HX-Request": "true", "HX-Boosted": "true", "HX-Current-URL": "http://testserver/yaks"},
            HTTPStatus.UNAUTHORIZED,
            "HX-Redirect",
            "/auth/login?redirect=/protected%3Fpage%3D2",
        ),
    ],
    ids=["path", "query", "htmx", "htmx-foreign", "boosted"],
)
def test_middleware_redirects_unauthenticated_users(  # noqa: PLR0913, PLR0917
    temp_user_file, method, url, headers, status, location_header, login_url
):
    """Unauthenticated requests are sent to login with a way back to where they were."""

    async def protected_endpoint(request):  # noqa: RUF029
        return Response("Protected content")

    app = Starlette(routes=[Route("/protected", endpoint=protected_endpoint, methods=["GET", "POST"]), *AUTH_ROUTES])
    app.add_middleware(AuthMiddleware, public_paths=AUTH_PUBLIC_PATHS)

    client = TestClient(app, follow_redirects=False)

    response = client.request(method, url, headers=headers)
    assert response.status_code == status
    assert response.headers.get(location_header) == login_url


def test_middleware_allows_authenticated_users(sample_user):
    """Test that middleware allows authenticated users to access protected paths."""

    async def protected_endpoint(request):  # noqa: RUF029
        return Response("Protected content")

    app = Starlette(routes=[Route("/protected", endpoint=protected_endpoint), *AUTH_ROUTES])
    app.add_middleware(AuthMiddleware, public_paths=AUTH_PUBLIC_PATHS)
    client = TestClient(app, follow_redirects=False)

    post_login(client)

    response = client.get("/protected")
    assert response.status_code == HTTPStatus.OK
    assert b"Protected content" in response.content
    # Back-forward cache would otherwise show the page again after logout
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(("logged_in", "status"), [(True, HTTPStatus.NO_CONTENT), (False, HTTPStatus.SEE_OTHER)])
def test_session_check(auth_client, sample_user, logged_in, status):
    """A resumed page asks this before showing notes; the middleware is what answers."""
    if logged_in:
        post_login(auth_client)

    assert auth_client.get("/api/session").status_code == status


def test_middleware_validates_public_paths_format(temp_user_file):
    """Test that middleware raises ValueError when public paths don't start with '^'."""
    app = Starlette(routes=AUTH_ROUTES)

    with pytest.raises(ValueError, match=r"Public paths must be regular expressions and start with '\^'"):
        AuthMiddleware(app=app, public_paths={"/auth/login", "^/auth/status"})
