from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from yak_shears.constants import DEFAULT_REDIRECT
from yak_shears.server.routes import ROUTES, not_found


@pytest.fixture
def app() -> Starlette:
    """Create a test Starlette application.

    Returns:
        Starlette: A test Starlette application
    """
    return Starlette(routes=ROUTES, debug=True, exception_handlers={404: not_found})


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

    assert response.status_code == HTTPStatus.TEMPORARY_REDIRECT
    assert response.headers["location"] == DEFAULT_REDIRECT


@pytest.fixture
def mock_djot_files() -> list[Path]:
    """Create mock Djot files for testing.

    Returns:
        list[Path]: List of mock file paths
    """
    mock_dir = Path(__file__).parent / "test_data/mock_djot_files"
    return [
        mock_dir / "file1.dj",
        mock_dir / "file2.dj",
        mock_dir / "subdirectory/file3.dj",
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
                assert response.status_code == HTTPStatus.OK
                assert "file1.dj" in response.text
                assert "file2.dj" in response.text
                assert "file3.dj" in response.text


def test_not_found(client: TestClient, mock_user_session) -> None:
    """Test the 404 handler."""
    response = client.get("/non_existent_endpoint")
    assert response.status_code == HTTPStatus.NOT_FOUND
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
                assert response.status_code == HTTPStatus.OK
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
                assert response.status_code == HTTPStatus.SEE_OTHER
                assert response.headers["location"] == "/edit?file=/path/to/test.dj"
                mock_write_text.assert_called_once_with("Updated content", encoding="utf-8")


def test_edit_file_not_found(client: TestClient, mock_user_session) -> None:
    """Test the edit file endpoint with non-existent file."""
    with patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = False

        response = client.get("/edit?file=/path/to/nonexistent.dj")
        assert response.status_code == HTTPStatus.NOT_FOUND
        assert "File not found" in response.text


def test_edit_file_no_file_specified(client: TestClient, mock_user_session) -> None:
    """Test the edit file endpoint with no file specified."""
    response = client.get("/edit")
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "No file specified" in response.text


# Tests for auth endpoints
def test_auth_login_get(client: TestClient) -> None:
    """Test the login endpoint with GET request."""
    response = client.get("/auth/login")
    assert response.status_code == HTTPStatus.OK
    assert "<title>Login</title>" in response.text


def test_auth_status_not_logged_in(client: TestClient) -> None:
    """Test the auth status endpoint when not logged in."""
    response = client.get("/auth/status")
    assert response.status_code == HTTPStatus.OK
    json_response = response.json()
    assert json_response["authenticated"] is False


def test_auth_status_logged_in(client: TestClient, mock_user_session) -> None:
    """Test the auth status endpoint when logged in."""
    response = client.get("/auth/status")
    assert response.status_code == HTTPStatus.OK
    json_response = response.json()
    assert json_response["authenticated"] is True
    assert json_response["displayName"] == "Test User"


def test_auth_middleware_public_path(client: TestClient, mock_user_session) -> None:
    """Test that auth middleware allows access to public paths."""
    response = client.get("/auth/status")
    assert response.status_code == HTTPStatus.OK
