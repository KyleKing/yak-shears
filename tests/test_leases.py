"""Every write path refuses to act on a page that no longer matches the file.

Each test renders the page, takes the lease it published, changes the file behind
the app's back the way Syncthing would, and then submits the action the stale page
was offering.
"""

import re
from http import HTTPStatus

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from tests.conftest import set_yak_shears_dir
from yak_shears.server._routes import ROUTES

TASK = """---
type: task
state: queue
stream: work/ship
---

# Ship the importer
"""

STREAM = """---
type: stream
id: ship
name: Ship
---

# Ship
"""

LIST = """---
type: list
name: Groceries
---

# Groceries

## Produce

- [ ] apples
- [ ] pears
"""

HABIT = """---
type: habit
name: Stretch
schedule: daily
---

# Stretch
"""


def _lease(html: str, name: str) -> str:
    match = re.search(rf'name="{re.escape(name)}" value="([0-9a-f]+)"', html)
    assert match, f"no {name} lease published in the rendered page"
    return match[1]


@pytest.fixture
def client() -> TestClient:
    return TestClient(Starlette(routes=ROUTES, debug=True), follow_redirects=False)


@pytest.fixture
def vault(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "ship.dj").write_text(STREAM)
    (work / "task.dj").write_text(TASK)
    (work / "groceries.dj").write_text(LIST)
    (work / "stretch.dj").write_text(HABIT)
    return tmp_path


def test_board_action_refuses_a_stale_latch(client: TestClient, mock_user_session, vault) -> None:
    with set_yak_shears_dir(vault):
        page = client.get("/streams")
        lease = _lease(page.text, "lease:work/task.dj")

        (vault / "work" / "task.dj").write_text(TASK.replace("state: queue", "state: backlog"))

        response = client.post(
            "/streams/act",
            data={"path": "work/task.dj", "action": "advance", "lease:work/task.dj": lease},
            follow_redirects=False,
        )
        assert response.status_code == HTTPStatus.CONFLICT
        assert "changed since this page loaded" in response.text
        assert "state: backlog" in (vault / "work" / "task.dj").read_text()


def test_board_action_applies_with_a_current_latch(client: TestClient, mock_user_session, vault) -> None:
    with set_yak_shears_dir(vault):
        page = client.get("/streams")
        lease = _lease(page.text, "lease:work/task.dj")

        response = client.post(
            "/streams/act",
            data={"path": "work/task.dj", "action": "advance", "lease:work/task.dj": lease},
            follow_redirects=False,
        )
        assert response.status_code == HTTPStatus.SEE_OTHER
        assert "state: in-progress" in (vault / "work" / "task.dj").read_text()


def test_list_toggle_refuses_a_stale_ordinal(client: TestClient, mock_user_session, vault) -> None:
    with set_yak_shears_dir(vault):
        page = client.get("/lists")
        lease = _lease(page.text, "lease")

        (vault / "work" / "groceries.dj").write_text(LIST.replace("- [ ] apples", "- [ ] apples\n- [ ] bread"))

        response = client.post(
            "/lists/toggle",
            data={"path": "work/groceries.dj", "ordinal": "0", "lease": lease},
            follow_redirects=False,
        )
        assert response.status_code == HTTPStatus.CONFLICT
        assert "changed since this page loaded" in response.text
        assert "- [ ] apples" in (vault / "work" / "groceries.dj").read_text()


def test_list_toggle_applies_with_a_current_lease(client: TestClient, mock_user_session, vault) -> None:
    with set_yak_shears_dir(vault):
        page = client.get("/lists")
        lease = _lease(page.text, "lease")

        response = client.post(
            "/lists/toggle",
            data={"path": "work/groceries.dj", "ordinal": "0", "lease": lease},
            follow_redirects=False,
        )
        assert response.status_code in {HTTPStatus.OK, HTTPStatus.SEE_OTHER}
        assert "- [x] apples" in (vault / "work" / "groceries.dj").read_text()


def test_habit_toggle_refuses_a_stale_page(client: TestClient, mock_user_session, vault) -> None:
    with set_yak_shears_dir(vault):
        page = client.get("/habits")
        lease = _lease(page.text, "lease")

        (vault / "work" / "stretch.dj").write_text(HABIT + "\n- [x] 2026-01-01\n")

        response = client.post(
            "/habits/toggle",
            data={"path": "work/stretch.dj", "lease": lease},
            follow_redirects=False,
        )
        assert response.status_code == HTTPStatus.CONFLICT
        assert "changed since this page loaded" in response.text
