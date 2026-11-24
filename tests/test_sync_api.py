"""The sync API a native client uses, exercised through the real app and real auth."""

from collections.abc import Generator
from http import HTTPStatus
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from yak_shears._yak.services import yak_lease
from yak_shears.server._routes import create_app

from .conftest import SAMPLE_USER_EMAIL, SAMPLE_USER_PASSWORD, set_yak_shears_dir

EXISTING = "notes/2026-07-22T14_03_51Z.dj"
NEW = "notes/2026-11-21T09_15_00Z.dj"


@pytest.fixture
def vault(tmp_path: Path) -> Generator[Path, None, None]:
    """A vault with one note, one root note, and a Syncthing backup that must stay hidden.

    Yields:
        The vault directory, with the app pointed at it.
    """
    (tmp_path / "notes").mkdir()
    (tmp_path / EXISTING).write_text("# Existing\n", encoding="utf-8")
    (tmp_path / "2026-01-01T00_00_00Z.dj").write_text("root", encoding="utf-8")
    (tmp_path / ".stversions").mkdir()
    (tmp_path / ".stversions" / "old~20260101.dj").write_text("backup", encoding="utf-8")
    with set_yak_shears_dir(tmp_path):
        yield tmp_path


@pytest.fixture
def client(sample_user, vault: Path) -> TestClient:
    """A client of the production app, with auth middleware and no session.

    Returns:
        Test client that does not follow redirects.
    """
    return TestClient(create_app(), follow_redirects=False)


@pytest.fixture
def authed(client: TestClient) -> TestClient:
    """The same client carrying a bearer token obtained through the API.

    Returns:
        Test client whose requests send `Authorization: Bearer`.
    """
    response = client.post("/api/v1/token", json={"email": SAMPLE_USER_EMAIL, "password": SAMPLE_USER_PASSWORD})
    assert response.status_code == HTTPStatus.CREATED
    client.headers["Authorization"] = f"Bearer {response.json()['token']}"
    return client


@pytest.mark.parametrize(
    ("body", "expected_status"),
    [
        ({"email": SAMPLE_USER_EMAIL, "password": "wrong"}, HTTPStatus.UNAUTHORIZED),
        ({"email": SAMPLE_USER_EMAIL}, HTTPStatus.BAD_REQUEST),
        (["not", "an", "object"], HTTPStatus.BAD_REQUEST),
    ],
    ids=["wrong-password", "missing-password", "not-an-object"],
)
def test_token_refuses_bad_credentials(client: TestClient, body, expected_status) -> None:
    response = client.post("/api/v1/token", json=body)
    assert response.status_code == expected_status
    assert "token" not in response.json()


def test_api_answers_401_rather_than_redirecting_to_login(client: TestClient) -> None:
    response = client.get("/api/v1/yaks")
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_revoked_token_stops_authorizing(authed: TestClient) -> None:
    assert authed.get("/api/v1/yaks").status_code == HTTPStatus.OK
    # The bearer authorizes the web routes too, which is how the app reaches /media/upload.
    assert authed.get("/yaks").status_code == HTTPStatus.OK
    assert authed.delete("/api/v1/token").status_code == HTTPStatus.NO_CONTENT
    assert authed.get("/api/v1/yaks").status_code == HTTPStatus.UNAUTHORIZED
    assert authed.get("/yaks").status_code == HTTPStatus.TEMPORARY_REDIRECT
    assert authed.delete("/api/v1/token").status_code == HTTPStatus.UNAUTHORIZED


def test_manifest_lists_leases_and_skips_hidden_directories(authed: TestClient) -> None:
    yaks = authed.get("/api/v1/yaks").json()["yaks"]
    assert [(yak["path"], yak["lease"]) for yak in yaks] == [
        ("2026-01-01T00_00_00Z.dj", yak_lease("root")),
        (EXISTING, yak_lease("# Existing\n")),
    ]
    assert all(yak["modified"].endswith("+00:00") for yak in yaks)


@pytest.mark.parametrize(
    ("path", "expected_status"),
    [(EXISTING, HTTPStatus.OK), ("notes/missing.dj", HTTPStatus.NOT_FOUND), ("../outside.dj", HTTPStatus.NOT_FOUND)],
    ids=["exists", "missing", "traversal"],
)
def test_get_yak_carries_its_lease_as_the_etag(authed: TestClient, path: str, expected_status) -> None:
    response = authed.get(f"/api/v1/yaks/{path}")
    assert response.status_code == expected_status
    if expected_status == HTTPStatus.OK:
        assert response.text == "# Existing\n"
        assert response.headers["ETag"] == f'"{yak_lease("# Existing\n")}"'


@pytest.mark.parametrize(
    ("path", "headers", "expected"),
    [
        (NEW, {"If-None-Match": "*"}, (HTTPStatus.CREATED, "mine")),
        ("2026-11-21T09_15_00Z.dj", {"If-None-Match": "*"}, (HTTPStatus.CREATED, "mine")),
        (EXISTING, {"If-None-Match": "*"}, (HTTPStatus.PRECONDITION_FAILED, "# Existing\n")),
        ("notes/hand-named.dj", {"If-None-Match": "*"}, (HTTPStatus.BAD_REQUEST, None)),
        ("a/b/2026-11-21T09_15_00Z.dj", {"If-None-Match": "*"}, (HTTPStatus.BAD_REQUEST, None)),
        (".stversions/2026-11-21T09_15_00Z.dj", {"If-None-Match": "*"}, (HTTPStatus.BAD_REQUEST, None)),
        (EXISTING, {"If-Match": f'"{yak_lease("# Existing\n")}"'}, (HTTPStatus.OK, "mine")),
        (EXISTING, {"If-Match": '"0000000000000000"'}, (HTTPStatus.PRECONDITION_FAILED, "# Existing\n")),
        (EXISTING, {}, (HTTPStatus.PRECONDITION_REQUIRED, "# Existing\n")),
        ("notes/2020-01-01T00_00_00Z.dj", {"If-Match": '"0000000000000000"'}, (HTTPStatus.NOT_FOUND, None)),
    ],
    ids=[
        "create-in-category",
        "create-in-root",
        "create-over-existing",
        "create-non-canonical",
        "create-too-deep",
        "create-hidden",
        "update-current-lease",
        "update-stale-lease",
        "update-without-precondition",
        "update-deleted",
    ],
)
def test_put_is_always_conditional(
    authed: TestClient, vault: Path, path: str, headers: dict[str, str], expected: tuple[HTTPStatus, str | None]
) -> None:
    expected_status, expected_on_disk = expected
    response = authed.put(f"/api/v1/yaks/{path}", content=b"mine", headers=headers)
    assert response.status_code == expected_status
    on_disk = vault / path
    assert (on_disk.read_text(encoding="utf-8") if on_disk.is_file() else None) == expected_on_disk
    if expected_status in {HTTPStatus.OK, HTTPStatus.CREATED}:
        assert response.headers["ETag"] == f'"{yak_lease("mine")}"'
    if expected_status == HTTPStatus.PRECONDITION_FAILED:
        # The conflict carries what is on disk and the lease that would overwrite it.
        assert response.text == expected_on_disk
        assert response.headers["ETag"] == f'"{yak_lease(expected_on_disk)}"'


def test_created_yak_appears_in_the_manifest_with_its_lease(authed: TestClient) -> None:
    created = authed.put(f"/api/v1/yaks/{NEW}", content=b"mine", headers={"If-None-Match": "*"})
    manifest = {yak["path"]: yak["lease"] for yak in authed.get("/api/v1/yaks").json()["yaks"]}
    assert f'"{manifest[NEW]}"' == created.headers["ETag"]


@pytest.mark.parametrize(
    ("path", "headers", "expected"),
    [
        (EXISTING, {"If-Match": f'"{yak_lease("# Existing\n")}"'}, (HTTPStatus.NO_CONTENT, False)),
        (EXISTING, {"If-Match": '"0000000000000000"'}, (HTTPStatus.PRECONDITION_FAILED, True)),
        (EXISTING, {}, (HTTPStatus.PRECONDITION_REQUIRED, True)),
        ("notes/2020-01-01T00_00_00Z.dj", {"If-Match": '"0000000000000000"'}, (HTTPStatus.NOT_FOUND, False)),
    ],
    ids=["current-lease", "stale-lease", "without-precondition", "already-gone"],
)
def test_delete_needs_the_current_lease(
    authed: TestClient, vault: Path, path: str, headers: dict[str, str], expected: tuple[HTTPStatus, bool]
) -> None:
    expected_status, still_exists = expected
    response = authed.delete(f"/api/v1/yaks/{path}", headers=headers)
    assert response.status_code == expected_status
    assert (vault / path).is_file() == still_exists
