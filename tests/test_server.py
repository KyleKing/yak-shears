# TODO: Split up into file/routes

from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup
from starlette.applications import Starlette
from starlette.testclient import TestClient

from yak_shears._constants import DEFAULT_REDIRECT
from yak_shears._yak.database import get_search_db_path
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


def test_yaks_endpoint(client: TestClient, mock_user_session, snapshot) -> None:
    """Test the yaks endpoint."""
    with (
        set_yak_shears_dir(MOCK_YAK_DIR),
        patch("yak_shears._yak.services.datetime") as mock_datetime,
    ):
        mock_datetime.fromtimestamp.return_value = datetime(2025, 5, 1, 10, 0, 0, tzinfo=UTC)
        mock_datetime.UTC = UTC
        mock_datetime.now.return_value = datetime(2025, 5, 1, 10, 0, 0, tzinfo=UTC)

        response = client.get("/yaks")
        assert response.status_code == HTTPStatus.OK
        assert BeautifulSoup(response.content.decode("utf-8"), "html.parser").prettify() == snapshot()
        assert "yak1.dj" in response.text
        assert "yak2.dj" in response.text
        assert "yak3.dj" in response.text


def test_search_endpoint(client: TestClient, mock_user_session) -> None:
    """Test the search endpoint."""
    Path(get_search_db_path()).unlink(missing_ok=True)
    with set_yak_shears_dir(MOCK_YAK_DIR):
        response = client.get("/search?query=test")
        assert response.status_code == HTTPStatus.OK
        assert "Search Yaks" in response.text


def test_search_indexing_with_temp_db(tmp_path, client: TestClient, mock_user_session) -> None:
    """Test search indexing with temporary database and generated test data."""
    # Create test yak files with specific content
    yak_dir = tmp_path / "yaks"
    yak_dir.mkdir()
    db_dir = tmp_path / "db"
    db_dir.mkdir()

    # Create test files
    (yak_dir / "file1.dj").write_text("apple banana\ncherry")
    (yak_dir / "file2.dj").write_text("apple dog\nbanana")
    (yak_dir / "subdir").mkdir()
    (yak_dir / "subdir" / "file3.dj").write_text("elephant apple")

    with (
        patch.dict("os.environ", {"YAK_SHEARS_DIR": str(yak_dir), "SEARCH_DB_DIR": str(db_dir)}),
        patch("yak_shears._yak.database.time") as mock_time,
    ):
        mock_time.time.return_value = 1000.0

        # First search - should index
        response = client.get("/search?query=apple")
        assert response.status_code == HTTPStatus.OK

        # Modify a file
        (yak_dir / "file1.dj").write_text("apple banana\nmodified")

        # Second search - should update index
        mock_time.time.return_value = 1001.0  # After interval
        response = client.get("/search?query=modified")
        assert response.status_code == HTTPStatus.OK

        # Delete a file
        (yak_dir / "file2.dj").unlink()

        # Third search - should remove deleted
        mock_time.time.return_value = 1002.0
        response = client.get("/search?query=dog")
        assert response.status_code == HTTPStatus.OK


def test_not_found(client: TestClient, mock_user_session) -> None:
    """Test the 404 handler."""
    response = client.get("/non_existent_endpoint")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert "Not Found" in response.text


def test_edit_yak_get(client: TestClient, mock_user_session, tmp_path, snapshot) -> None:
    """Test the edit yak endpoint with GET request."""
    # Create a temporary yak
    test_yak = tmp_path / "test.dj"
    test_yak.write_text("Test yak content")

    with set_yak_shears_dir(tmp_path):
        response = client.get("/edit?yak=test.dj")
        assert response.status_code == HTTPStatus.OK
        assert "Editing test.dj" in response.text
        assert "Test yak content" in response.text
        assert BeautifulSoup(response.content.decode("utf-8"), "html.parser").prettify() == snapshot()


def test_edit_yak_post(client: TestClient, mock_user_session, tmp_path) -> None:
    """Test the edit yak endpoint with POST request."""
    # Create a temporary yak
    test_yak = tmp_path / "test.dj"
    test_yak.write_text("Original content")

    with set_yak_shears_dir(tmp_path):
        response = client.post(
            "/edit",
            data={"yak": "test.dj", "content": "Updated content"},
            headers={"HX-Request": "true"},
        )
        assert response.status_code == HTTPStatus.OK
        assert not response.text
        assert test_yak.read_text() == "Updated content"


def test_edit_yak_not_found(client: TestClient, mock_user_session, tmp_path) -> None:
    """Test the edit yak endpoint with non-existent yak."""
    with set_yak_shears_dir(tmp_path):
        response = client.get("/edit?yak=nonexistent.dj")
        assert response.status_code == HTTPStatus.NOT_FOUND
        assert "Yak not found: " in response.text


def test_edit_yak_no_yak_specified(client: TestClient, mock_user_session) -> None:
    """Test the edit yak endpoint with no yak specified."""
    response = client.get("/edit")
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "No `yak` path specified" in response.text


def test_new_yak_get(client: TestClient, mock_user_session) -> None:
    """Test the new yak endpoint GET."""
    with set_yak_shears_dir(MOCK_YAK_DIR):
        response = client.get("/new")
        assert response.status_code == HTTPStatus.OK
        assert "New Yak" in response.text


def test_new_yak_post(client: TestClient, mock_user_session, tmp_path) -> None:
    """Test the new yak endpoint POST."""
    with set_yak_shears_dir(tmp_path):
        response = client.post("/new", data={"category": "test"})
        assert response.status_code == HTTPStatus.SEE_OTHER
        location = response.headers["location"]
        assert location.startswith("/edit?yak=")
        yak_path_str = location.split("=", 1)[1]
        yak_path = tmp_path / yak_path_str
        assert yak_path.exists()
        assert not yak_path.read_text()


def test_new_yak_post_no_category(client: TestClient, mock_user_session, tmp_path) -> None:
    """Test the new yak endpoint POST with no category."""
    with set_yak_shears_dir(tmp_path):
        response = client.post("/new", data={})
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert "Category is required" in response.text


def test_yak_preview(client: TestClient, mock_user_session) -> None:
    """Test the yak preview endpoint."""
    with set_yak_shears_dir(MOCK_YAK_DIR):
        response = client.get("/api/yak-preview?path=subdirectory-2/yak2.dj&line=1&query=test")
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert "html" in data


def test_yak_preview_no_path(client: TestClient, mock_user_session) -> None:
    """Test the yak preview endpoint with no path."""
    with set_yak_shears_dir(MOCK_YAK_DIR):
        response = client.get("/api/yak-preview")
        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "Path required" in data["error"]


def test_yak_preview_not_found(client: TestClient, mock_user_session) -> None:
    """Test the yak preview endpoint with nonexistent file."""
    with set_yak_shears_dir(MOCK_YAK_DIR):
        response = client.get("/api/yak-preview?path=nonexistent.dj")
        assert response.status_code == HTTPStatus.NOT_FOUND
        data = response.json()
        assert "File not found" in data["error"]


def test_search_htmx_empty(client: TestClient, mock_user_session) -> None:
    """Test the search endpoint with HTMX and no query."""
    with set_yak_shears_dir(MOCK_YAK_DIR):
        response = client.get("/search", headers={"HX-Request": "true"})
        assert response.status_code == HTTPStatus.OK
        assert "Start typing" in response.text


def test_search_htmx_with_query(client: TestClient, mock_user_session) -> None:
    """Test the search endpoint with HTMX and query."""
    with set_yak_shears_dir(MOCK_YAK_DIR):
        response = client.get("/search?query=test", headers={"HX-Request": "true"})
        assert response.status_code == HTTPStatus.OK


@pytest.mark.parametrize("sort_by", ["name", "modified"])
def test_yaks_sort(client: TestClient, mock_user_session, sort_by) -> None:
    """Test the yaks endpoint with different sort options."""
    with set_yak_shears_dir(MOCK_YAK_DIR):
        response = client.get(f"/yaks?sort_by={sort_by}")
        assert response.status_code == HTTPStatus.OK
        assert "yak1.dj" in response.text


def test_yaks_invalid_page(client: TestClient, mock_user_session) -> None:
    """Test the yaks endpoint with invalid page."""
    with set_yak_shears_dir(MOCK_YAK_DIR):
        response = client.get("/yaks?page=invalid")
        assert response.status_code == HTTPStatus.OK


def test_yaks_invalid_sort_by(client: TestClient, mock_user_session) -> None:
    """Test the yaks endpoint with invalid sort_by."""
    with set_yak_shears_dir(MOCK_YAK_DIR):
        response = client.get("/yaks?sort_by=invalid")
        assert response.status_code == HTTPStatus.OK


def test_yaks_invalid_category(client: TestClient, mock_user_session) -> None:
    """Test the yaks endpoint with invalid category."""
    with set_yak_shears_dir(MOCK_YAK_DIR):
        response = client.get("/yaks?category=invalid")
        assert response.status_code == HTTPStatus.OK


def test_yaks_with_category(client: TestClient, mock_user_session) -> None:
    """Test the yaks endpoint with category filter."""
    with set_yak_shears_dir(MOCK_YAK_DIR):
        response = client.get("/yaks?category=subdirectory-2")
        assert response.status_code == HTTPStatus.OK
        assert "yak2.dj" in response.text
        assert "yak1.dj" not in response.text


def test_yaks_empty_dir(client: TestClient, mock_user_session, tmp_path) -> None:
    """Test the yaks endpoint with empty directory."""
    with set_yak_shears_dir(tmp_path):
        response = client.get("/yaks")
        assert response.status_code == HTTPStatus.OK


def test_edit_yak_post_no_hx(client: TestClient, mock_user_session, tmp_path) -> None:
    """Test the edit yak endpoint POST without HX-Request."""
    test_yak = tmp_path / "test.dj"
    test_yak.write_text("Original")
    with set_yak_shears_dir(tmp_path):
        response = client.post("/edit?yak=test.dj", data={"content": "Updated"})
        assert response.status_code == HTTPStatus.OK
        assert test_yak.read_text() == "Updated"  # updated


def test_delete_yak(client: TestClient, mock_user_session, tmp_path) -> None:
    """Test the delete yak endpoint."""
    test_yak = tmp_path / "test.dj"
    test_yak.write_text("Content")
    with set_yak_shears_dir(tmp_path):
        response = client.post("/delete", data={"yak": "test.dj"})
        assert response.status_code == HTTPStatus.OK
        assert "HX-Redirect" in response.headers
        assert response.headers["HX-Redirect"] == "/yaks"
        assert not test_yak.exists()


def test_delete_yak_not_found(client: TestClient, mock_user_session, tmp_path) -> None:
    """Test the delete yak endpoint with nonexistent yak."""
    with set_yak_shears_dir(tmp_path):
        response = client.post("/delete", data={"yak": "nonexistent.dj"})
        assert response.status_code == HTTPStatus.NOT_FOUND
        assert "Yak not found" in response.text


def test_delete_yak_no_yak_specified(client: TestClient, mock_user_session) -> None:
    """Test the delete yak endpoint with no yak specified."""
    response = client.post("/delete", data={})
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "No `yak` path specified" in response.text
