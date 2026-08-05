# TODO: Split up into file/routes

import os
import re
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

import pytest
from freezegun import freeze_time
from starlette.applications import Starlette
from starlette.testclient import TestClient

from yak_shears import _templates
from yak_shears._constants import DEFAULT_REDIRECT
from yak_shears._yak.database import get_search_db_path
from yak_shears._yak.services import yak_lease
from yak_shears.server._handlers import not_found
from yak_shears.server._routes import ROUTES, create_app, create_app_without_auth

from .conftest import MOCK_YAK_DIR, set_yak_shears_dir, stable_html


@pytest.fixture
def isolated_yak_dir(tmp_path: Path) -> Path:
    """Create an isolated yak directory for snapshot testing.

    Returns:
        Path: Temporary directory with 3 test yak files
    """
    test_dir = tmp_path / "yak_test_dir"
    test_dir.mkdir()

    (test_dir / "subdirectory-2").mkdir()
    (test_dir / "subdirectory-3").mkdir()

    (test_dir / "yak1.dj").write_text("# Yak 1\n\n<https://www.ecosia.org/search?method=index&q=yak>", encoding="utf-8")
    (test_dir / "subdirectory-2" / "yak2.dj").write_text("# Yak 2\n\n<https://www.ecosia.org/search?method=index&q=yak>", encoding="utf-8")
    (test_dir / "subdirectory-3" / "yak3.dj").write_text("# Yak 3\n\nThis is a test yak number 3", encoding="utf-8")

    return test_dir


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


def test_static_url_versions_and_busts_on_change(tmp_path, monkeypatch) -> None:
    """static_url fingerprints assets, reuses the token until the file changes."""
    css = tmp_path / "css"
    css.mkdir()
    asset = css / "x.css"
    asset.write_text("a{}")
    monkeypatch.setattr(_templates, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(_templates, "_static_versions", {})

    url = _templates.static_url("css/x.css")
    assert re.fullmatch(r"/static/css/x\.css\?v=[0-9a-f]{8}", url)
    assert _templates.static_url("css/x.css") == url

    asset.write_text("a{color:red}")
    os.utime(asset, (asset.stat().st_atime + 10, asset.stat().st_mtime + 10))
    assert _templates.static_url("css/x.css") != url


def test_static_url_missing_asset_is_unversioned(tmp_path, monkeypatch) -> None:
    """A missing asset falls back to a bare URL instead of raising."""
    monkeypatch.setattr(_templates, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(_templates, "_static_versions", {})
    assert _templates.static_url("css/missing.css") == "/static/css/missing.css"


def test_dev_static_files_revalidate() -> None:
    """Local dev serves static assets with no-cache so edits are picked up."""
    dev_client = TestClient(create_app_without_auth())
    response = dev_client.get("/static/css/main.css")
    assert response.status_code == HTTPStatus.OK
    assert response.headers["cache-control"] == "no-cache"


def test_prod_static_files_are_immutable() -> None:
    """Production serves fingerprinted assets with a long immutable cache."""
    prod_client = TestClient(create_app())
    response = prod_client.get("/static/css/main.css")
    assert response.status_code == HTTPStatus.OK
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_yaks_endpoint(client: TestClient, mock_user_session, isolated_yak_dir: Path, snapshot) -> None:
    """Test the yaks endpoint."""
    with (
        set_yak_shears_dir(isolated_yak_dir),
        freeze_time("2025-05-01 10:00:00", tz_offset=0),
        patch("yak_shears._yak.services.datetime") as mock_datetime,
    ):
        mock_datetime.fromtimestamp.return_value.strftime.return_value = "2025-05-01 10:00:00"
        mock_datetime.fromtimestamp.return_value = datetime(2025, 5, 1, 10, 0, 0, tzinfo=UTC)
        mock_datetime.now.return_value = datetime(2025, 5, 1, 10, 0, 0, tzinfo=UTC)

        response = client.get("/yaks")
        assert response.status_code == HTTPStatus.OK
        assert stable_html(response.content) == snapshot()
        assert "yak1.dj" in response.text
        assert "yak2.dj" in response.text
        assert "yak3.dj" in response.text


def test_search_endpoint(client: TestClient, mock_user_session) -> None:
    """Test the search endpoint.

    NOT SAFE FOR PARALLEL: Deletes shared database file.
    TODO: Refactor to use isolated tmp_path with proper DB fixture.
    """
    Path(get_search_db_path()).unlink(missing_ok=True)
    with set_yak_shears_dir(MOCK_YAK_DIR):
        response = client.get("/search?query=test")
        assert response.status_code == HTTPStatus.OK
        assert "Search Yaks" in response.text


def test_search_initial_indexing(tmp_path, client: TestClient, mock_user_session) -> None:
    """Test that search performs initial indexing on first query."""
    yak_dir = tmp_path / "yaks"
    yak_dir.mkdir()
    db_dir = tmp_path / "db"
    db_dir.mkdir()

    (yak_dir / "file1.dj").write_text("apple banana\ncherry")
    (yak_dir / "file2.dj").write_text("apple dog\nbanana")

    with (
        patch.dict("os.environ", {"YAK_SHEARS_DIR": str(yak_dir), "SEARCH_DB_DIR": str(db_dir)}),
        freeze_time("2025-01-01 00:00:00"),
    ):
        response = client.get("/search?query=apple")
        assert response.status_code == HTTPStatus.OK


def test_search_reindexes_modified_files(tmp_path, client: TestClient, mock_user_session) -> None:
    """Test that search reindexes files when they are modified."""
    yak_dir = tmp_path / "yaks"
    yak_dir.mkdir()
    db_dir = tmp_path / "db"
    db_dir.mkdir()

    (yak_dir / "file1.dj").write_text("apple banana\ncherry")

    with (
        patch.dict("os.environ", {"YAK_SHEARS_DIR": str(yak_dir), "SEARCH_DB_DIR": str(db_dir)}),
        freeze_time("2025-01-01 00:00:00") as frozen_time,
    ):
        # Initial indexing
        client.get("/search?query=apple")

        # Modify file
        (yak_dir / "file1.dj").write_text("apple banana\nmodified")

        # Search should reindex and find new content
        frozen_time.tick()
        response = client.get("/search?query=modified")
        assert response.status_code == HTTPStatus.OK


def test_search_removes_deleted_files_from_index(tmp_path, client: TestClient, mock_user_session) -> None:
    """Test that search removes deleted files from the index."""
    yak_dir = tmp_path / "yaks"
    yak_dir.mkdir()
    db_dir = tmp_path / "db"
    db_dir.mkdir()

    (yak_dir / "file1.dj").write_text("apple banana")
    (yak_dir / "file2.dj").write_text("apple dog")

    with (
        patch.dict("os.environ", {"YAK_SHEARS_DIR": str(yak_dir), "SEARCH_DB_DIR": str(db_dir)}),
        freeze_time("2025-01-01 00:00:00") as frozen_time,
    ):
        # Initial indexing
        client.get("/search?query=apple")

        # Delete file
        (yak_dir / "file2.dj").unlink()

        # Search should update index to remove deleted file
        frozen_time.tick()
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
        assert stable_html(response.content) == snapshot()


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



def _published_lease(html: str) -> str:
    """The lease the edit page rendered, which a save has to send back."""
    match = re.search(r'id="yak-lease" data-lease="([^"]+)"', html)
    assert match, "the edit page published no lease"
    return match[1]


def test_edit_yak_post_refuses_a_stale_lease(client: TestClient, mock_user_session, tmp_path) -> None:
    """A write whose lease no longer matches the file is refused, not merged or forced."""
    test_yak = tmp_path / "test.dj"
    test_yak.write_text("Original content")

    with set_yak_shears_dir(tmp_path):
        opened = client.get("/edit?yak=test.dj")
        lease = _published_lease(opened.text)

        test_yak.write_text("Changed by another device")

        response = client.post(
            "/edit",
            data={"yak": "test.dj", "content": "Updated content", "lease": lease},
            headers={"HX-Request": "true"},
        )
        assert response.status_code == HTTPStatus.CONFLICT
        assert test_yak.read_text() == "Changed by another device"
        # The editor diffs against this rather than only reporting that they differ,
        # and the returned lease is the one a deliberate overwrite has to present.
        assert response.text == "Changed by another device"
        assert response.headers["X-Yak-Lease"] == yak_lease("Changed by another device")

        forced = client.post(
            "/edit",
            data={"yak": "test.dj", "content": "Mine wins", "lease": response.headers["X-Yak-Lease"]},
        )
        assert forced.status_code == HTTPStatus.OK
        assert test_yak.read_text() == "Mine wins"


def test_edit_yak_post_returns_a_lease_that_permits_the_next_save(
    client: TestClient, mock_user_session, tmp_path
) -> None:
    """Saving twice without reloading works, because each response carries the new lease."""
    test_yak = tmp_path / "test.dj"
    test_yak.write_text("Original content")

    with set_yak_shears_dir(tmp_path):
        opened = client.get("/edit?yak=test.dj")
        lease = _published_lease(opened.text)

        first = client.post("/edit", data={"yak": "test.dj", "content": "One", "lease": lease})
        assert first.status_code == HTTPStatus.OK

        second = client.post(
            "/edit",
            data={"yak": "test.dj", "content": "Two", "lease": first.headers["X-Yak-Lease"]},
        )
        assert second.status_code == HTTPStatus.OK
        assert test_yak.read_text() == "Two"


@pytest.mark.parametrize(
    ("endpoint", "method", "query_or_data", "use_tmp_path", "expected_status", "expected_text"),
    [
        ("/edit", "get", "yak=nonexistent.dj", True, HTTPStatus.NOT_FOUND, "Yak not found: "),
        ("/edit", "get", "", False, HTTPStatus.BAD_REQUEST, "No `yak` path specified"),
        ("/delete", "post", "yak=nonexistent.dj", True, HTTPStatus.NOT_FOUND, "Yak not found"),
        ("/delete", "post", "", False, HTTPStatus.BAD_REQUEST, "No `yak` path specified"),
    ],
    ids=["edit_not_found", "edit_no_yak", "delete_not_found", "delete_no_yak"],
)
def test_yak_endpoint_errors(
    client: TestClient,
    mock_user_session,
    tmp_path,
    endpoint,
    method,
    query_or_data,
    use_tmp_path,
    expected_status,
    expected_text,
) -> None:
    """Test edit and delete endpoint error cases (not found, missing yak param)."""
    context = set_yak_shears_dir(tmp_path) if use_tmp_path else None
    if context:
        with context:
            if method == "get":
                url = f"{endpoint}?{query_or_data}" if query_or_data else endpoint
                response = client.get(url)
            else:
                data = {"yak": query_or_data.split("=")[1]} if query_or_data else {}
                response = client.post(endpoint, data=data)
            assert response.status_code == expected_status
            assert expected_text in response.text
    else:
        if method == "get":
            url = f"{endpoint}?{query_or_data}" if query_or_data else endpoint
            response = client.get(url)
        else:
            data = {"yak": query_or_data.split("=")[1]} if query_or_data else {}
            response = client.post(endpoint, data=data)
        assert response.status_code == expected_status
        assert expected_text in response.text


def test_new_yak_get_renders_the_category_keys(client: TestClient, mock_user_session) -> None:
    """Test that the new yak endpoint GET renders the picker on its own page."""
    with set_yak_shears_dir(MOCK_YAK_DIR):
        response = client.get("/new")
        assert response.status_code == HTTPStatus.OK
        assert 'class="new-yak__key"' in response.text
        assert 'name="new_category"' in response.text


def test_yaks_does_not_carry_the_new_yak_form(client: TestClient, mock_user_session) -> None:
    """Test that the rack no longer pays to render the creation form."""
    with set_yak_shears_dir(MOCK_YAK_DIR):
        response = client.get("/yaks")
        assert response.status_code == HTTPStatus.OK
        assert 'name="new_category"' not in response.text


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
        assert "source" in data
        assert data["query"] == "test"
        assert data["edit_url"].startswith("/edit?yak=")


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


@pytest.mark.parametrize("sort_by", ["created_at", "modified"])
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


def test_doctor_reports_and_fixes_mixed_filenames(client: TestClient, tmp_path: Path) -> None:
    """Doctor surfaces legacy names and the fix action renames them in place."""
    vault = tmp_path / "vault"
    (vault / "evergreen").mkdir(parents=True)
    (vault / "evergreen" / "20250930_153525.dj").write_text("legacy note", encoding="utf-8")
    (vault / "evergreen" / "meeting-notes.dj").write_text("see [[20250930_153525]]", encoding="utf-8")

    with set_yak_shears_dir(vault), patch.dict(os.environ, {"SEARCH_DB_DIR": str(tmp_path / "state")}):
        listed = client.get("/doctor")
        assert listed.status_code == HTTPStatus.OK
        assert "20250930_153525.dj" in listed.text
        assert "2025-09-30T15_35_25Z.dj" in listed.text
        # A hand-written name is reported but never proposed for renaming.
        assert "meeting-notes.dj" in listed.text

        fixed = client.post("/doctor/fix-filenames")
        assert fixed.status_code == HTTPStatus.SEE_OTHER

    assert not (vault / "evergreen" / "20250930_153525.dj").exists()
    assert (vault / "evergreen" / "2025-09-30T15_35_25Z.dj").read_text() == "legacy note"
    assert (vault / "evergreen" / "meeting-notes.dj").read_text() == "see [[2025-09-30T15_35_25Z]]"


def test_doctor_fix_is_a_noop_when_names_are_canonical(client: TestClient, tmp_path: Path) -> None:
    """Pressing fix with nothing to do redirects without touching the vault."""
    vault = tmp_path / "vault"
    (vault / "evergreen").mkdir(parents=True)
    canonical = vault / "evergreen" / "2026-07-22T14_03_51Z.dj"
    canonical.write_text("already fine", encoding="utf-8")

    with set_yak_shears_dir(vault), patch.dict(os.environ, {"SEARCH_DB_DIR": str(tmp_path / "state")}):
        response = client.post("/doctor/fix-filenames")

    assert response.status_code == HTTPStatus.SEE_OTHER
    assert canonical.read_text() == "already fine"
