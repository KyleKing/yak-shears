from http import HTTPStatus

import pytest
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route
from starlette.testclient import TestClient

from yak_shears.auth.middleware import AuthMiddleware
from yak_shears.auth.routes import DEFAULT_REDIRECT
from yak_shears.auth.routes import PUBLIC_PATHS as AUTH_PUBLIC_PATHS
from yak_shears.auth.routes import ROUTES as AUTH_ROUTES

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


class TestLoginEndpoint:
    """Test the login endpoint."""

    @pytest.mark.parametrize(
        ("email", "password", "expected_content"),
        [
            (SAMPLE_USER_EMAIL, "wrong_password", b"Invalid email or password"),
            ("nonexistent@example.com", "password", b"Invalid email or password"),
            (None, "password", b"Email and password are required"),
            (SAMPLE_USER_EMAIL, None, b"Email and password are required"),
            ("", "password", b"Email and password are required"),
            (SAMPLE_USER_EMAIL, "", b"Email and password are required"),
        ],
        ids=[
            "Invalid Password",
            "Non-existent user",
            "Missing Email",
            "Missing Password",
            "Empty Email",
            "Empty Password",
        ],
    )
    def test_login_errors(self, auth_client, sample_user, email, password, expected_content):
        """Test login POST requests with various input errors."""
        response = auth_client.post("/auth/login", data={"email": email, "password": password})

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert expected_content in response.content

    def test_login_get_shows_form(self, auth_client):
        """Test that GET /auth/login shows the login form."""
        response = auth_client.get("/auth/login")

        assert response.status_code == HTTPStatus.OK
        assert "text/html" in response.headers["content-type"]
        assert b"email" in response.content.lower()
        assert b"password" in response.content.lower()

    def test_login_handles_newlines_in_input(self, auth_client, sample_user):
        """Test that login handles newlines in email/password input."""
        response = auth_client.post(
            "/auth/login",
            data={"email": SAMPLE_USER_EMAIL + "\n", "password": SAMPLE_USER_PASSWORD + "\n"},
        )

        # Should still work (newlines should be stripped)
        assert response.status_code == HTTPStatus.SEE_OTHER
        assert response.headers["location"] == DEFAULT_REDIRECT

    def test_login_keeps_redirect(self, auth_client, sample_user):
        """Test that login keeps the redirect."""
        response = auth_client.post(
            "/auth/login",
            data={"redirect": "/page/abc", "email": SAMPLE_USER_EMAIL, "password": SAMPLE_USER_PASSWORD},
        )

        assert response.status_code == HTTPStatus.SEE_OTHER
        assert response.headers["location"] == "/page/abc"


class TestLogoutEndpoint:
    """Test the logout endpoint."""

    def test_logout_get(self, auth_client, sample_user):
        """Test GET /auth/logout."""
        login_response = auth_client.post(
            "/auth/login",
            data={"email": SAMPLE_USER_EMAIL, "password": SAMPLE_USER_PASSWORD},
        )
        assert login_response.status_code == HTTPStatus.SEE_OTHER

        # Then log out
        logout_response = auth_client.get("/auth/logout")

        # Should redirect to home
        assert logout_response.status_code == HTTPStatus.TEMPORARY_REDIRECT
        assert logout_response.headers["location"] == "/home"

        # Session cookie should be deleted
        session_cookies = [cookie for cookie in logout_response.cookies if cookie == "session_id"]
        assert len(session_cookies) == 0

    def test_logout_when_not_logged_in(self, auth_client):
        """Test logout when not logged in."""
        response = auth_client.get("/auth/logout")

        # Should still redirect (graceful handling)
        assert response.status_code == HTTPStatus.TEMPORARY_REDIRECT
        assert response.headers["location"] == "/home"


class TestStatusEndpoint:
    """Test the authentication status endpoint."""

    def test_status_when_not_logged_in(self, auth_client):
        """Test /auth/status when not authenticated."""
        response = auth_client.get("/auth/status")

        assert response.status_code == HTTPStatus.OK
        assert response.headers["content-type"] == "application/json"

        data = response.json()
        assert data["authenticated"] is False

    def test_status_when_logged_in(self, auth_client, sample_user):
        """Test /auth/status when authenticated."""
        login_response = auth_client.post(
            "/auth/login",
            data={"email": SAMPLE_USER_EMAIL, "password": SAMPLE_USER_PASSWORD},
        )
        assert login_response.status_code == HTTPStatus.SEE_OTHER

        # Then check status
        status_response = auth_client.get("/auth/status")

        assert status_response.status_code == HTTPStatus.OK
        assert status_response.headers["content-type"] == "application/json"

        data = status_response.json()
        assert data["authenticated"] is True
        assert data["email"] == SAMPLE_USER_EMAIL

    def test_status_with_invalid_session(self, auth_client):
        """Test /auth/status with invalid session cookie."""
        # Set an invalid session cookie manually
        auth_client.cookies.set("session_id", "invalid-session-id")

        response = auth_client.get("/auth/status")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["authenticated"] is False


class TestAuthMiddleware:
    """Test the authentication middleware."""

    def test_middleware_allows_public_paths(self, temp_user_file):
        """Test that middleware allows access to public paths."""
        app = Starlette(routes=AUTH_ROUTES)
        app.add_middleware(AuthMiddleware, public_paths={"/auth/login", "/auth/status"})

        client = TestClient(app, follow_redirects=False)

        # Should allow access to public paths
        response = client.get("/auth/login")
        assert response.status_code == HTTPStatus.OK

        response = client.get("/auth/status")
        assert response.status_code == HTTPStatus.OK

    def test_middleware_redirects_unauthenticated_users(self, temp_user_file):
        """Test that middleware redirects unauthenticated users."""

        async def protected_endpoint(request):  # noqa: RUF029
            return Response("Protected content")

        app = Starlette(
            routes=[
                Route("/protected", endpoint=protected_endpoint),
                *AUTH_ROUTES,  # Replace auth_routes with AUTH_ROUTES
            ]
        )
        app.add_middleware(AuthMiddleware, public_paths={"/auth/login", "/auth/status"})

        client = TestClient(app, follow_redirects=False)

        # Should redirect to login
        response = client.get("/protected", follow_redirects=False)
        assert response.status_code == HTTPStatus.TEMPORARY_REDIRECT
        assert response.headers["location"] == "/auth/login?redirect=/protected"

    def test_middleware_allows_authenticated_users(self, sample_user):
        """Test that middleware allows authenticated users to access protected paths."""

        async def protected_endpoint(request):  # noqa: RUF029
            return Response("Protected content")

        app = Starlette(routes=[Route("/protected", endpoint=protected_endpoint), *AUTH_ROUTES])
        app.add_middleware(AuthMiddleware, public_paths={"/auth/login", "/auth/status"})

        client = TestClient(app, follow_redirects=False)

        login_response = client.post("/auth/login", data={"email": SAMPLE_USER_EMAIL, "password": SAMPLE_USER_PASSWORD})
        assert login_response.status_code == HTTPStatus.SEE_OTHER

        response = client.get("/protected")
        assert response.status_code == HTTPStatus.OK
        assert b"Protected content" in response.content


class TestSessionManagement:
    """Test session management in HTTP context."""

    def test_session_persists_across_requests(self, auth_client, sample_user):
        """Test that session persists across multiple requests."""
        login_response = auth_client.post(
            "/auth/login",
            data={"email": SAMPLE_USER_EMAIL, "password": SAMPLE_USER_PASSWORD},
        )
        assert login_response.status_code == HTTPStatus.SEE_OTHER

        # Make multiple status requests
        for _ in range(3):
            status_response = auth_client.get("/auth/status")
            assert status_response.status_code == HTTPStatus.OK

            data = status_response.json()
            assert data["authenticated"] is True
            assert data["email"] == SAMPLE_USER_EMAIL

    def test_session_expires_after_logout(self, auth_client, sample_user):
        """Test that session expires after logout."""
        login_response = auth_client.post(
            "/auth/login", data={"email": SAMPLE_USER_EMAIL, "password": SAMPLE_USER_PASSWORD}
        )
        assert login_response.status_code == HTTPStatus.SEE_OTHER

        # Verify logged in
        status_response = auth_client.get("/auth/status")
        data = status_response.json()
        assert data["authenticated"] is True

        # Log out
        logout_response = auth_client.get("/auth/logout")
        assert logout_response.status_code == HTTPStatus.TEMPORARY_REDIRECT

        # Verify logged out
        status_response = auth_client.get("/auth/status")
        data = status_response.json()
        assert data["authenticated"] is False


class TestErrorHandling:
    """Test error handling in authentication routes."""

    def test_malformed_form_data(self, auth_client):
        """Test handling of malformed form data."""
        # Send invalid form data
        response = auth_client.post(
            "/auth/login", headers={"content-type": "application/x-www-form-urlencoded"}, content=b"invalid\xff\xfe\xfd"
        )

        # Should handle gracefully (not crash)
        assert response.status_code in {HTTPStatus.OK, HTTPStatus.BAD_REQUEST}

    def test_very_large_form_data(self, auth_client):
        """Test handling of very large form data."""
        large_email = "a" * 10000 + "@example.com"
        large_password = "b" * 10000

        response = auth_client.post("/auth/login", data={"email": large_email, "password": large_password})

        # Should handle gracefully
        assert response.status_code == HTTPStatus.BAD_REQUEST
