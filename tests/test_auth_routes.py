"""Tests for authentication routes and HTTP endpoints."""

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from yak_shears.auth.middleware import AuthMiddleware
from yak_shears.auth.models import Password
from yak_shears.auth.routes import ROUTES as AUTH_ROUTES
from yak_shears.auth.storage import create_user
from yak_shears.server.routes import not_found


@pytest.fixture
def auth_app(temp_user_file):
    """Create a test app with authentication."""
    app = Starlette(
        routes=AUTH_ROUTES,
        debug=True,
        exception_handlers={404: not_found},
    )

    # Add auth middleware with public paths
    app.add_middleware(AuthMiddleware, public_paths={"/auth/login", "/auth/status"})

    return app


@pytest.fixture
def auth_client(auth_app):
    """Create a test client for the auth app."""
    return TestClient(auth_app)


@pytest.fixture
def sample_user(temp_user_file):
    """Create a sample user for testing."""
    email = "test@example.com"
    display_name = "Test User"
    password = Password("secure123")

    user = create_user(email, display_name, password)
    return {"user": user, "password": password}


class TestLoginEndpoint:
    """Test the login endpoint."""

    def test_login_get_shows_form(self, auth_client):
        """Test that GET /auth/login shows the login form."""
        response = auth_client.get("/auth/login")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"email" in response.content.lower()
        assert b"password" in response.content.lower()

    def test_login_post_valid_credentials(self, auth_client, sample_user):
        """Test login with valid credentials."""
        user_data = sample_user["user"]
        password = sample_user["password"]

        response = auth_client.post("/auth/login", data={"email": user_data["email"], "password": password})

        # Should redirect after successful login
        assert response.status_code == 303
        assert response.headers["location"] == "/home"

        # Should set session cookie
        assert "session_id" in [cookie.name for cookie in response.cookies]

    def test_login_post_invalid_credentials(self, auth_client, sample_user):
        """Test login with invalid credentials."""
        user_data = sample_user["user"]

        response = auth_client.post("/auth/login", data={"email": user_data["email"], "password": "wrong_password"})

        # Should show form with error
        assert response.status_code == 200
        assert b"Invalid email or password" in response.content

    def test_login_post_nonexistent_user(self, auth_client):
        """Test login with non-existent user."""
        response = auth_client.post("/auth/login", data={"email": "nonexistent@example.com", "password": "password"})

        # Should show form with error
        assert response.status_code == 200
        assert b"Invalid email or password" in response.content

    def test_login_post_missing_email(self, auth_client):
        """Test login with missing email."""
        response = auth_client.post("/auth/login", data={"password": "password"})

        # Should show form with error
        assert response.status_code == 200
        assert b"Email and password are required" in response.content

    def test_login_post_missing_password(self, auth_client):
        """Test login with missing password."""
        response = auth_client.post("/auth/login", data={"email": "test@example.com"})

        # Should show form with error
        assert response.status_code == 200
        assert b"Email and password are required" in response.content

    def test_login_post_empty_email(self, auth_client):
        """Test login with empty email."""
        response = auth_client.post("/auth/login", data={"email": "", "password": "password"})

        # Should show form with error
        assert response.status_code == 200
        assert b"Email and password are required" in response.content

    def test_login_post_empty_password(self, auth_client):
        """Test login with empty password."""
        response = auth_client.post("/auth/login", data={"email": "test@example.com", "password": ""})

        # Should show form with error
        assert response.status_code == 200
        assert b"Email and password are required" in response.content

    def test_login_get_when_already_logged_in(self, auth_client, sample_user):
        """Test GET /auth/login when already logged in."""
        user_data = sample_user["user"]
        password = sample_user["password"]

        # First, log in
        login_response = auth_client.post("/auth/login", data={"email": user_data["email"], "password": password})
        assert login_response.status_code == 303

        # Then try to access login page again
        response = auth_client.get("/auth/login")

        # Should redirect to home
        assert response.status_code == 303
        assert response.headers["location"] == "/home"

    def test_login_handles_newlines_in_input(self, auth_client, sample_user):
        """Test that login handles newlines in email/password input."""
        user_data = sample_user["user"]
        password = sample_user["password"]

        response = auth_client.post(
            "/auth/login",
            data={"email": user_data["email"] + "\n", "password": password + "\n"},
        )

        # Should still work (newlines should be stripped)
        assert response.status_code == 303
        assert response.headers["location"] == "/home"


class TestLogoutEndpoint:
    """Test the logout endpoint."""

    def test_logout_get(self, auth_client, sample_user):
        """Test GET /auth/logout."""
        user_data = sample_user["user"]
        password = sample_user["password"]

        # First, log in
        login_response = auth_client.post("/auth/login", data={"email": user_data["email"], "password": password})
        assert login_response.status_code == 303

        # Then log out
        logout_response = auth_client.get("/auth/logout")

        # Should redirect to home
        assert logout_response.status_code == 303
        assert logout_response.headers["location"] == "/home"

        # Session cookie should be deleted
        session_cookies = [cookie for cookie in logout_response.cookies if cookie.name == "session_id"]
        assert len(session_cookies) == 1
        assert session_cookies[0].value == ""  # Cookie deletion sets empty value

    def test_logout_post(self, auth_client, sample_user):
        """Test POST /auth/logout."""
        user_data = sample_user["user"]
        password = sample_user["password"]

        # First, log in
        login_response = auth_client.post("/auth/login", data={"email": user_data["email"], "password": password})
        assert login_response.status_code == 303

        # Then log out via POST
        logout_response = auth_client.post("/auth/logout")

        # Should redirect to home
        assert logout_response.status_code == 303
        assert logout_response.headers["location"] == "/home"

    def test_logout_when_not_logged_in(self, auth_client):
        """Test logout when not logged in."""
        response = auth_client.get("/auth/logout")

        # Should still redirect (graceful handling)
        assert response.status_code == 303
        assert response.headers["location"] == "/home"


class TestStatusEndpoint:
    """Test the authentication status endpoint."""

    def test_status_when_not_logged_in(self, auth_client):
        """Test /auth/status when not authenticated."""
        response = auth_client.get("/auth/status")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        data = response.json()
        assert data["authenticated"] is False

    def test_status_when_logged_in(self, auth_client, sample_user):
        """Test /auth/status when authenticated."""
        user_data = sample_user["user"]
        password = sample_user["password"]

        # First, log in
        login_response = auth_client.post("/auth/login", data={"email": user_data["email"], "password": password})
        assert login_response.status_code == 303

        # Then check status
        status_response = auth_client.get("/auth/status")

        assert status_response.status_code == 200
        assert status_response.headers["content-type"] == "application/json"

        data = status_response.json()
        assert data["authenticated"] is True
        assert data["email"] == user_data["email"]
        assert data["displayName"] == user_data["display_name"]

    def test_status_with_invalid_session(self, auth_client):
        """Test /auth/status with invalid session cookie."""
        # Set an invalid session cookie manually
        auth_client.cookies.set("session_id", "invalid-session-id")

        response = auth_client.get("/auth/status")

        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is False


class TestAuthMiddleware:
    """Test the authentication middleware."""

    def test_middleware_allows_public_paths(self, temp_user_file):
        """Test that middleware allows access to public paths."""
        app = Starlette(routes=AUTH_ROUTES)
        app.add_middleware(AuthMiddleware, public_paths={"/auth/login", "/auth/status"})

        client = TestClient(app)

        # Should allow access to public paths
        response = client.get("/auth/login")
        assert response.status_code == 200

        response = client.get("/auth/status")
        assert response.status_code == 200

    def test_middleware_redirects_unauthenticated_users(self, temp_user_file):
        """Test that middleware redirects unauthenticated users."""
        from starlette.responses import Response
        from starlette.routing import Route

        async def protected_endpoint(request):
            return Response("Protected content")

        app = Starlette(
            routes=[
                Route("/protected", endpoint=protected_endpoint),
                *AUTH_ROUTES,  # Replace auth_routes with AUTH_ROUTES
            ]
        )
        app.add_middleware(AuthMiddleware, public_paths={"/auth/login", "/auth/status"})

        client = TestClient(app)

        # Should redirect to login
        response = client.get("/protected", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/auth/login"

    def test_middleware_allows_authenticated_users(self, temp_user_file):
        """Test that middleware allows authenticated users to access protected paths."""
        from starlette.responses import Response
        from starlette.routing import Route

        # Create a user first
        create_user("test@example.com", "Test User", Password("password123"))

        async def protected_endpoint(request):
            return Response("Protected content")

        app = Starlette(routes=[Route("/protected", endpoint=protected_endpoint), *AUTH_ROUTES])
        app.add_middleware(AuthMiddleware, public_paths={"/auth/login", "/auth/status"})

        client = TestClient(app)

        # First log in
        login_response = client.post("/auth/login", data={"email": "test@example.com", "password": "password123"})
        assert login_response.status_code == 303

        # Then access protected endpoint
        response = client.get("/protected")
        assert response.status_code == 200
        assert b"Protected content" in response.content


class TestSessionManagement:
    """Test session management in HTTP context."""

    def test_session_persists_across_requests(self, auth_client, sample_user):
        """Test that session persists across multiple requests."""
        user_data = sample_user["user"]
        password = sample_user["password"]

        # Log in
        login_response = auth_client.post("/auth/login", data={"email": user_data["email"], "password": password})
        assert login_response.status_code == 303

        # Make multiple status requests
        for _ in range(3):
            status_response = auth_client.get("/auth/status")
            assert status_response.status_code == 200

            data = status_response.json()
            assert data["authenticated"] is True
            assert data["email"] == user_data["email"]

    def test_session_expires_after_logout(self, auth_client, sample_user):
        """Test that session expires after logout."""
        user_data = sample_user["user"]
        password = sample_user["password"]

        # Log in
        login_response = auth_client.post("/auth/login", data={"email": user_data["email"], "password": password})
        assert login_response.status_code == 303

        # Verify logged in
        status_response = auth_client.get("/auth/status")
        data = status_response.json()
        assert data["authenticated"] is True

        # Log out
        logout_response = auth_client.get("/auth/logout")
        assert logout_response.status_code == 303

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
        assert response.status_code in [200, 400]  # Either show form or bad request

    def test_very_large_form_data(self, auth_client):
        """Test handling of very large form data."""
        large_email = "a" * 10000 + "@example.com"
        large_password = "b" * 10000

        response = auth_client.post("/auth/login", data={"email": large_email, "password": large_password})

        # Should handle gracefully
        assert response.status_code == 200  # Should show error message
