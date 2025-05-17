"""Tests for the auth module using Starlette TestClient."""

import base64
import secrets
from unittest.mock import MagicMock, patch

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from yak_shears import auth


@pytest.fixture
def mock_user() -> auth.User:
    """Create a mock user for testing.

    Returns:
        auth.User: A mock user
    """
    return {
        "id": "test_user_id",
        "name": "test_user",
        "display_name": "Test User",
        "credentials": [
            {
                "id": "test_credential_id",
                "public_key": base64.b64encode(b"test_public_key").decode(),
                "sign_count": 0,
                "transports": ["internal"],
            }
        ],
        "current_challenge": None,
    }


@pytest.fixture
def auth_app() -> Starlette:
    """Create a test Starlette application with auth routes.

    Returns:
        Starlette: A test Starlette application
    """
    async def protected_handler(request: Request) -> Response:
        return JSONResponse({"message": "This is a protected endpoint"})

    async def public_handler(request: Request) -> Response:
        return JSONResponse({"message": "This is a public endpoint"})

    app = Starlette(
        routes=[
            Route("/protected", endpoint=protected_handler),
            Route("/public", endpoint=public_handler),
        ] + auth.auth_routes,
        debug=True,
    )

    # Add auth middleware
    public_paths = ["/public", "/auth/login", "/auth/register", "/auth/status"]
    app.add_middleware(auth.AuthMiddleware, public_paths=public_paths)

    return app


@pytest.fixture
def auth_client(auth_app: Starlette) -> TestClient:
    """Create a TestClient for the auth application.

    Args:
        auth_app: The Starlette application with auth routes

    Returns:
        TestClient: A test client for the application
    """
    return TestClient(auth_app)


def test_generate_user_id() -> None:
    """Test _generate_user_id creates a valid hex string."""
    user_id = auth._generate_user_id()
    assert isinstance(user_id, str)
    assert len(user_id) == 32  # 16 bytes as hex = 32 chars
    # Ensure it's a valid hex string
    int(user_id, 16)


def test_generate_session_id() -> None:
    """Test _generate_session_id creates a valid hex string."""
    session_id = auth._generate_session_id()
    assert isinstance(session_id, str)
    assert len(session_id) == 64  # 32 bytes as hex = 64 chars
    # Ensure it's a valid hex string
    int(session_id, 16)


def test_create_user() -> None:
    """Test create_user creates a user with the expected fields."""
    # Patch _save_users to avoid writing to disk during tests
    with patch.object(auth, "_save_users"):
        username = "testuser"
        display_name = "Test User"
        user = auth.create_user(username, display_name)

        assert user["name"] == username
        assert user["display_name"] == display_name
        assert user["credentials"] == []
        assert user["current_challenge"] is None
        assert isinstance(user["id"], str)

        # Check that the user was added to the _users dict
        assert auth._users[user["id"]] == user
        assert auth._username_to_user_id[username] == user["id"]


def test_get_user_by_name() -> None:
    """Test get_user_by_name returns the correct user."""
    # Patch _save_users to avoid writing to disk during tests
    with patch.object(auth, "_save_users"):
        # Create a test user
        username = "testuser"
        display_name = "Test User"
        user = auth.create_user(username, display_name)

        # Test getting the user by name
        retrieved_user = auth.get_user_by_name(username)
        assert retrieved_user == user

        # Test getting a non-existent user
        assert auth.get_user_by_name("nonexistent") is None


def test_get_user_by_id() -> None:
    """Test get_user_by_id returns the correct user."""
    # Patch _save_users to avoid writing to disk during tests
    with patch.object(auth, "_save_users"):
        # Create a test user
        username = "testuser"
        display_name = "Test User"
        user = auth.create_user(username, display_name)

        # Test getting the user by ID
        retrieved_user = auth.get_user_by_id(user["id"])
        assert retrieved_user == user

        # Test getting a non-existent user
        assert auth.get_user_by_id("nonexistent") is None


def test_add_credential_to_user(mock_user: auth.User) -> None:
    """Test add_credential_to_user adds a credential to the user.

    Args:
        mock_user: A mock user for testing
    """
    # Patch _save_users to avoid writing to disk during tests
    with patch.object(auth, "_save_users"):
        # Add the mock user to _users
        auth._users[mock_user["id"]] = mock_user

        # Create a new credential
        new_credential: auth.CredentialEntry = {
            "id": "new_credential_id",
            "public_key": base64.b64encode(b"new_public_key").decode(),
            "sign_count": 0,
            "transports": ["internal"],
        }

        # Add the credential to the user
        auth.add_credential_to_user(mock_user["id"], new_credential)

        # Check that the credential was added
        assert new_credential in auth._users[mock_user["id"]]["credentials"]


def test_update_credential_sign_count(mock_user: auth.User) -> None:
    """Test update_credential_sign_count updates the sign count.

    Args:
        mock_user: A mock user for testing
    """
    # Patch _save_users to avoid writing to disk during tests
    with patch.object(auth, "_save_users"):
        # Add the mock user to _users
        auth._users[mock_user["id"]] = mock_user

        # Update the sign count
        auth.update_credential_sign_count(mock_user["id"], "test_credential_id", 5)

        # Check that the sign count was updated
        for cred in auth._users[mock_user["id"]]["credentials"]:
            if cred["id"] == "test_credential_id":
                assert cred["sign_count"] == 5
                break


def test_create_session() -> None:
    """Test create_session creates a session and adds it to _session_store."""
    user_id = "test_user_id"
    session_id = auth.create_session(user_id)

    assert isinstance(session_id, str)
    assert auth._session_store[session_id] == user_id


def test_delete_session() -> None:
    """Test delete_session removes a session from _session_store."""
    # Create a session
    user_id = "test_user_id"
    session_id = auth.create_session(user_id)

    # Delete the session
    auth.delete_session(session_id)

    # Check that the session was removed
    assert session_id not in auth._session_store


def test_get_user_from_session() -> None:
    """Test get_user_from_session returns the correct user."""
    # Patch _save_users to avoid writing to disk during tests
    with patch.object(auth, "_save_users"):
        # Create a test user
        username = "testuser"
        display_name = "Test User"
        user = auth.create_user(username, display_name)

        # Create a session
        session_id = auth.create_session(user["id"])

        # Create a mock request with the session cookie
        mock_request = MagicMock(spec=Request)
        mock_request.cookies = {"session_id": session_id}

        # Test getting the user from the session
        with patch.object(auth, "get_user_by_id", return_value=user):
            retrieved_user = auth.get_user_from_session(mock_request)
            assert retrieved_user == user

        # Test with an invalid session ID
        mock_request.cookies = {"session_id": "invalid"}
        retrieved_user = auth.get_user_from_session(mock_request)
        assert retrieved_user is None

        # Test with no session ID
        mock_request.cookies = {}
        retrieved_user = auth.get_user_from_session(mock_request)
        assert retrieved_user is None


def test_generate_auth_options_for_user(mock_user: auth.User) -> None:
    """Test generate_auth_options_for_user generates authentication options.

    Args:
        mock_user: A mock user for testing
    """
    # Patch _save_users to avoid writing to disk during tests
    with patch.object(auth, "_save_users"):
        # Patch get_user_by_name to return the mock user
        with patch.object(auth, "get_user_by_name", return_value=mock_user):
            # Patch secrets.token_bytes to return a fixed challenge
            with patch.object(secrets, "token_bytes", return_value=b"test_challenge"):
                options, user = auth.generate_auth_options_for_user(mock_user["name"])

                assert user == mock_user
                assert options is not None
                assert options.challenge == b"test_challenge"
                assert mock_user["current_challenge"] == base64.b64encode(b"test_challenge").decode()


def test_auth_middleware_public_path(auth_client: TestClient) -> None:
    """Test that auth middleware allows access to public paths.

    Args:
        auth_client: The test client for the auth app
    """
    # Ensure get_user_from_session returns None (not logged in)
    with patch.object(auth, "get_user_from_session", return_value=None):
        # Public paths should be accessible
        response = auth_client.get("/public")
        assert response.status_code == 200
        assert response.json() == {"message": "This is a public endpoint"}


def test_auth_middleware_protected_path(auth_client: TestClient) -> None:
    """Test that auth middleware redirects to login for protected paths.

    Args:
        auth_client: The test client for the auth app
    """
    # Ensure get_user_from_session returns None (not logged in)
    with patch.object(auth, "get_user_from_session", return_value=None):
        # Protected paths should redirect to login
        response = auth_client.get("/protected")
        assert response.status_code == 303
        assert response.headers["location"] == "/auth/login"


def test_auth_middleware_authenticated(auth_client: TestClient, mock_user: auth.User) -> None:
    """Test that auth middleware allows authenticated users to access protected paths.

    Args:
        auth_client: The test client for the auth app
        mock_user: A mock user for testing
    """
    # Ensure get_user_from_session returns the mock user (logged in)
    with patch.object(auth, "get_user_from_session", return_value=mock_user):
        # Protected paths should be accessible
        response = auth_client.get("/protected")
        assert response.status_code == 200
        assert response.json() == {"message": "This is a protected endpoint"}
