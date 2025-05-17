"""Tests for the API endpoints using Starlette TestClient."""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from yak_shears import auth
from yak_shears.server import (
    not_found,
    routes,
)


@pytest.fixture
def app() -> Starlette:
    """Create a test Starlette application.

    Returns:
        Starlette: A test Starlette application
    """
    # Create app with auth middleware
    app = Starlette(
        routes=routes,
        debug=True,
        exception_handlers={404: not_found},
    )

    # Wrap app with auth middleware
    public_paths = ["/", "/home", "/auth/login", "/auth/register", "/auth/status"]
    app.add_middleware(auth.AuthMiddleware, public_paths=public_paths)

    return app


@pytest.fixture
def client(app: Starlette) -> TestClient:
    """Create a TestClient for the Starlette application.

    Args:
        app: The Starlette application

    Returns:
        TestClient: A test client for the application
    """
    return TestClient(app)


def test_root_endpoint(client: TestClient) -> None:
    """Test the root endpoint redirects to home.

    Args:
        client: The test client
    """
    response = client.get("/")
    assert response.status_code == 307  # Temporary redirect
    assert response.headers["location"] == "/home"


def test_home_endpoint_not_logged_in(client: TestClient) -> None:
    """Test the home endpoint when not logged in.

    Args:
        client: The test client
    """
    response = client.get("/home")
    assert response.status_code == 200
    assert "Not logged in" in response.text
    assert "Login" in response.text
    assert "Register" in response.text


def test_home_endpoint_logged_in(client: TestClient) -> None:
    """Test the home endpoint when logged in.

    Args:
        client: The test client
    """
    # Create a mock user and session
    with patch.object(auth, "get_user_from_session") as mock_get_user:
        mock_user = {
            "id": "test_user_id",
            "name": "test_user",
            "display_name": "Test User",
            "credentials": [],
            "current_challenge": None,
        }
        mock_get_user.return_value = mock_user

        response = client.get("/home")
        assert response.status_code == 200
        assert "Logged in as:" in response.text
        assert "Test User" in response.text
        assert "Logout" in response.text


def test_echo_endpoint_get(client: TestClient) -> None:
    """Test the echo endpoint with GET request.

    Args:
        client: The test client
    """
    response = client.get("/echo?param1=value1&param2=value2")
    assert response.status_code == 200
    assert "Echo" in response.text
    assert "URL Parameters" in response.text
    assert "param1" in response.text
    assert "value1" in response.text
    assert "param2" in response.text
    assert "value2" in response.text


def test_echo_endpoint_post_json(client: TestClient) -> None:
    """Test the echo endpoint with POST request sending JSON.

    Args:
        client: The test client
    """
    test_data = {"key1": "value1", "key2": ["item1", "item2"]}
    response = client.post(
        "/echo",
        json=test_data,
    )
    assert response.status_code == 200
    assert "Echo" in response.text
    assert "JSON Payload" in response.text
    assert json.dumps(test_data, indent=2) in response.text


def test_echo_endpoint_post_raw(client: TestClient) -> None:
    """Test the echo endpoint with POST request sending raw data.

    Args:
        client: The test client
    """
    test_data = "This is raw POST data"
    response = client.post(
        "/echo",
        content=test_data,
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 200
    assert "Echo" in response.text
    assert "Raw POST Data" in response.text
    assert test_data in response.text


def test_time_endpoint(client: TestClient) -> None:
    """Test the time endpoint returns current time.

    Args:
        client: The test client
    """
    # Mock datetime.now to return a fixed time
    fixed_time = datetime(2025, 5, 22, 12, 34, 56, tzinfo=UTC)
    with patch("yak_shears.server.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_time
        # Ensure UTC is passed through
        mock_datetime.UTC = UTC

        response = client.get("/time")
        assert response.status_code == 200
        assert "Current Time" in response.text
        assert "2025-05-22 12:34:56" in response.text


@pytest.fixture
def mock_djot_files() -> list[Path]:
    """Create mock Djot files for testing.

    Returns:
        list[Path]: List of mock file paths
    """
    # Mock file paths
    return [
        Path("/home/user/Sync/yak-shears/file1.dj"),
        Path("/home/user/Sync/yak-shears/file2.dj"),
        Path("/home/user/Sync/yak-shears/subdirectory/file3.dj"),
    ]


def test_files_endpoint(client: TestClient, mock_djot_files: list[Path]) -> None:
    """Test the files endpoint.

    Args:
        client: The test client
        mock_djot_files: Mock file paths
    """
    # Mock the get_djot_files function
    with patch("yak_shears.server.get_djot_files") as mock_get_files:
        mock_get_files.return_value = (mock_djot_files, 3, 1)

        # Mock Path.stat for each file
        with patch("pathlib.Path.stat") as mock_stat:

            class MockStat:
                st_size = 1024
                st_mtime = datetime(2025, 5, 1, 10, 0, 0, tzinfo=UTC).timestamp()

            mock_stat.return_value = MockStat()

            # Mock datetime.fromtimestamp
            with patch("yak_shears.server.datetime") as mock_datetime:
                mock_datetime.fromtimestamp.return_value = datetime(2025, 5, 1, 10, 0, 0, tzinfo=UTC)
                mock_datetime.UTC = UTC

                response = client.get("/files")
                assert response.status_code == 200
                assert "Files in" in response.text
                assert "file1.dj" in response.text
                assert "file2.dj" in response.text
                assert "file3.dj" in response.text


def test_not_found(client: TestClient) -> None:
    """Test the 404 handler.

    Args:
        client: The test client
    """
    response = client.get("/non_existent_endpoint")
    assert response.status_code == 404
    assert "404 Not Found" in response.text


def test_edit_file_get(client: TestClient) -> None:
    """Test the edit file endpoint with GET request.

    Args:
        client: The test client
    """
    # Mock file path and read_text
    with patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = True
        with patch("pathlib.Path.is_file") as mock_is_file:
            mock_is_file.return_value = True
            with patch("pathlib.Path.read_text") as mock_read_text:
                mock_read_text.return_value = "Test file content"

                response = client.get("/edit?file=/path/to/test.dj")
                assert response.status_code == 200
                assert "Editing test.dj" in response.text
                assert "Test file content" in response.text


def test_edit_file_post(client: TestClient) -> None:
    """Test the edit file endpoint with POST request.

    Args:
        client: The test client
    """
    # Mock file path, exists, is_file, and write_text
    with patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = True
        with patch("pathlib.Path.is_file") as mock_is_file:
            mock_is_file.return_value = True
            with patch("pathlib.Path.write_text") as mock_write_text:
                mock_write_text.return_value = None

                response = client.post(
                    "/edit?file=/path/to/test.dj",
                    data={"content": "Updated content"},
                )
                assert response.status_code == 303  # See Other redirect
                assert response.headers["location"] == "/edit?file=/path/to/test.dj"
                mock_write_text.assert_called_once_with("Updated content")


def test_edit_file_not_found(client: TestClient) -> None:
    """Test the edit file endpoint with non-existent file.

    Args:
        client: The test client
    """
    with patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = False

        response = client.get("/edit?file=/path/to/nonexistent.dj")
        assert response.status_code == 404
        assert "File not found" in response.text


def test_edit_file_no_file_specified(client: TestClient) -> None:
    """Test the edit file endpoint with no file specified.

    Args:
        client: The test client
    """
    response = client.get("/edit")
    assert response.status_code == 400
    assert "No file specified" in response.text


# Tests for auth endpoints
def test_auth_login_get(client: TestClient) -> None:
    """Test the login endpoint with GET request.

    Args:
        client: The test client
    """
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert "Login with Passkey" in response.text


def test_auth_register_get(client: TestClient) -> None:
    """Test the register endpoint with GET request.

    Args:
        client: The test client
    """
    response = client.get("/auth/register")
    assert response.status_code == 200
    assert "Register with Passkey" in response.text


def test_auth_status_not_logged_in(client: TestClient) -> None:
    """Test the auth status endpoint when not logged in.

    Args:
        client: The test client
    """
    response = client.get("/auth/status")
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["authenticated"] is False


def test_auth_status_logged_in(client: TestClient) -> None:
    """Test the auth status endpoint when logged in.

    Args:
        client: The test client
    """
    # Create a mock user and session
    with patch.object(auth, "get_user_from_session") as mock_get_user:
        mock_user = {
            "id": "test_user_id",
            "name": "test_user",
            "display_name": "Test User",
            "credentials": [],
            "current_challenge": None,
        }
        mock_get_user.return_value = mock_user

        response = client.get("/auth/status")
        assert response.status_code == 200
        json_response = response.json()
        assert json_response["authenticated"] is True
        assert json_response["username"] == "test_user"
        assert json_response["displayName"] == "Test User"


def test_auth_middleware_public_path(client: TestClient) -> None:
    """Test that auth middleware allows access to public paths.

    Args:
        client: The test client
    """
    # Ensure get_user_from_session returns None (not logged in)
    with patch.object(auth, "get_user_from_session") as mock_get_user:
        mock_get_user.return_value = None

        # Public paths should be accessible
        response = client.get("/home")
        assert response.status_code == 200


def test_auth_middleware_protected_path(client: TestClient) -> None:
    """Test that auth middleware redirects to login for protected paths.

    Args:
        client: The test client
    """
    # Ensure get_user_from_session returns None (not logged in)
    with patch.object(auth, "get_user_from_session") as mock_get_user:
        mock_get_user.return_value = None

        # Protected paths should redirect to login
        response = client.get("/files")
        assert response.status_code == 303
        assert response.headers["location"] == "/auth/login"
