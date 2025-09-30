# TODO: Split up into file/routes

from datetime import UTC, datetime
from http import HTTPStatus
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup
from starlette.applications import Starlette
from starlette.testclient import TestClient

from yak_shears._constants import DEFAULT_REDIRECT
from yak_shears.server._handlers import not_found
from yak_shears.server._routes import ROUTES

from .conftest import MOCK_YAK_DIR, set_yak_shears_dir


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


def test_files_endpoint(client: TestClient, mock_user_session, snapshot) -> None:
    """Test the files endpoint."""
    with (
        set_yak_shears_dir(MOCK_YAK_DIR),
        patch("yak_shears._file.handlers.datetime") as mock_datetime,
    ):
        mock_datetime.fromtimestamp.return_value = datetime(2025, 5, 1, 10, 0, 0, tzinfo=UTC)
        mock_datetime.UTC = UTC

        response = client.get("/files")
        assert response.status_code == HTTPStatus.OK
        assert BeautifulSoup(response.content.decode("utf-8"), "html.parser").prettify() == snapshot()
        assert "file1.dj" in response.text
        assert "file2.dj" in response.text
        assert "file3.dj" in response.text


def test_not_found(client: TestClient, mock_user_session) -> None:
    """Test the 404 handler."""
    response = client.get("/non_existent_endpoint")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert "Not Found" in response.text


def test_edit_file_get(client: TestClient, mock_user_session, tmp_path, snapshot) -> None:
    """Test the edit file endpoint with GET request."""
    # Create a temporary file
    test_file = tmp_path / "test.dj"
    test_file.write_text("Test file content")

    with set_yak_shears_dir(tmp_path):
        response = client.get("/edit?yak=test.dj")
        assert response.status_code == HTTPStatus.OK
        assert "Editing test.dj" in response.text
        assert "Test file content" in response.text
        assert BeautifulSoup(response.content.decode("utf-8"), "html.parser").prettify() == snapshot()


def test_edit_file_post(client: TestClient, mock_user_session, tmp_path) -> None:
    """Test the edit file endpoint with POST request."""
    # Create a temporary file
    test_file = tmp_path / "test.dj"
    test_file.write_text("Original content")

    with set_yak_shears_dir(tmp_path):
        response = client.post(
            "/edit",
            data={"yak": "test.dj", "content": "Updated content"},
            headers={"HX-Request": "true"},
        )
        assert response.status_code == HTTPStatus.OK
        assert response.text == ""
        assert test_file.read_text() == "Updated content"


def test_edit_file_not_found(client: TestClient, mock_user_session, tmp_path) -> None:
    """Test the edit file endpoint with non-existent file."""
    with set_yak_shears_dir(tmp_path):
        response = client.get("/edit?yak=nonexistent.dj")
        assert response.status_code == HTTPStatus.NOT_FOUND
        assert "Yak not found: " in response.text


def test_edit_file_no_file_specified(client: TestClient, mock_user_session) -> None:
    """Test the edit file endpoint with no file specified."""
    response = client.get("/edit")
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "No `yak` path specified" in response.text
