"""Tests for the API endpoints using Starlette TestClient."""

import json
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from yak_shears.auth.middleware import AuthMiddleware
from yak_shears.server.routes import ROUTES, not_found


@pytest.fixture
def app() -> Starlette:
    """Create a test Starlette application.

    Returns:
        Starlette: A test Starlette application
    """
    # TODO: merge with regular app definition?
    app = Starlette(
        routes=ROUTES,
        debug=True,
        exception_handlers={404: not_found},
    )
    public_paths = {"/", "/home", "/auth/login", "/auth/status"}
    app.add_middleware(AuthMiddleware, public_paths=public_paths)
    return app


@pytest.fixture
def client(app: Starlette) -> TestClient:
    """Create a TestClient for the Starlette application.

    Args:
        app: The Starlette application

    Returns:
        TestClient: A test client for the application
    """
    return TestClient(app, follow_redirects=False)


def test_root_endpoint(client: TestClient) -> None:
    """Test the root endpoint redirects to home."""
    response = client.get("/")
    assert response.status_code == 307
    assert response.headers["location"] == "/home"


def test_home_endpoint_not_logged_in(client: TestClient) -> None:
    """Test the home endpoint when not logged in."""
    response = client.get("/home")
    assert response.status_code == 200
    assert "Not logged in" in response.text
    assert "Login" in response.text


def test_home_endpoint_logged_in(client: TestClient, mock_user_session) -> None:
    """Test the home endpoint when logged in."""
    response = client.get("/home")
    assert response.status_code == 200
    assert "Logged in as:" in response.text
    assert "Test User" in response.text
    assert "Logout" in response.text


def test_echo_endpoint_get(client: TestClient, mock_user_session) -> None:
    """Test the echo endpoint with GET request."""
    response = client.get("/echo?param1=value1&param2=value2")
    assert response.status_code == 200
    assert "Echo" in response.text
    assert "URL Parameters" in response.text
    assert "param1" in response.text
    assert "value1" in response.text
    assert "param2" in response.text
    assert "value2" in response.text


def test_echo_endpoint_post_json(client: TestClient, mock_user_session) -> None:
    """Test the echo endpoint with POST request sending JSON."""
    test_data = {"key1": "value1", "key2": ["item1", "item2"]}
    response = client.post(
        "/echo",
        json=test_data,
    )
    assert response.status_code == 200
    assert "Echo" in response.text
    assert "JSON Payload" in response.text
    assert json.dumps(test_data, indent=2) in response.text


def test_echo_endpoint_post_raw(client: TestClient, mock_user_session) -> None:
    """Test the echo endpoint with POST request sending raw data."""
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


def test_time_endpoint(client: TestClient, mock_user_session) -> None:
    """Test the time endpoint returns current time."""
    fixed_time = datetime(2025, 5, 22, 12, 34, 56, tzinfo=UTC)
    with patch("yak_shears.server.handlers.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_time
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


def test_files_endpoint(client: TestClient, mock_djot_files: list[Path], mock_user_session) -> None:
    """Test the files endpoint."""
    with patch("yak_shears.server.handlers.get_djot_files") as mock_get_files:
        mock_get_files.return_value = (mock_djot_files, 3, 1)

        with patch("pathlib.Path.stat") as mock_stat:

            class MockStat:
                st_size = 1024
                st_mtime = datetime(2025, 5, 1, 10, 0, 0, tzinfo=UTC).timestamp()

            mock_stat.return_value = MockStat()

            with patch("yak_shears.server.handlers.datetime") as mock_datetime:
                mock_datetime.fromtimestamp.return_value = datetime(2025, 5, 1, 10, 0, 0, tzinfo=UTC)
                mock_datetime.UTC = UTC

                response = client.get("/files")
                assert response.status_code == 200
                assert "Files in" in response.text
                assert "file1.dj" in response.text
                assert "file2.dj" in response.text
                assert "file3.dj" in response.text


def test_not_found(client: TestClient, mock_user_session) -> None:
    """Test the 404 handler."""
    response = client.get("/non_existent_endpoint")
    assert response.status_code == 404
    assert "404 Not Found" in response.text


def test_edit_file_get(client: TestClient, mock_user_session) -> None:
    """Test the edit file endpoint with GET request."""
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


def test_edit_file_post(client: TestClient, mock_user_session) -> None:
    """Test the edit file endpoint with POST request."""
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
                assert response.status_code == 303
                assert response.headers["location"] == "/edit?file=/path/to/test.dj"
                mock_write_text.assert_called_once_with("Updated content")


def test_edit_file_not_found(client: TestClient, mock_user_session) -> None:
    """Test the edit file endpoint with non-existent file."""
    with patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = False

        response = client.get("/edit?file=/path/to/nonexistent.dj")
        assert response.status_code == 404
        assert "File not found" in response.text


def test_edit_file_no_file_specified(client: TestClient, mock_user_session) -> None:
    """Test the edit file endpoint with no file specified."""
    response = client.get("/edit")
    assert response.status_code == 400
    assert "No file specified" in response.text


# Tests for auth endpoints
def test_auth_login_get(client: TestClient) -> None:
    """Test the login endpoint with GET request."""
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert "<title>Login</title>" in response.text


def test_auth_status_not_logged_in(client: TestClient) -> None:
    """Test the auth status endpoint when not logged in."""
    response = client.get("/auth/status")
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["authenticated"] is False


def test_auth_status_logged_in(client: TestClient, mock_user_session) -> None:
    """Test the auth status endpoint when logged in."""
    response = client.get("/auth/status")
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["authenticated"] is True
    assert json_response["displayName"] == "Test User"


def test_auth_middleware_public_path(client: TestClient, mock_user_session) -> None:
    """Test that auth middleware allows access to public paths."""
    response = client.get("/home")
    assert response.status_code == 200


def test_auth_middleware_protected_path(client: TestClient) -> None:
    """Test that auth middleware redirects to login for protected paths."""
    response = client.get("/files")
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.headers["location"] == "/auth/login"
