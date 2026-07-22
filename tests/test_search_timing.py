"""Tests for the per-stage search timing instrumentation."""

import re
from http import HTTPStatus
from unittest.mock import patch

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from yak_shears._log_utils import StageTimer
from yak_shears._yak.database import close_search_db
from yak_shears.server._handlers import not_found
from yak_shears.server._routes import ROUTES

SEARCH_LINE_RE = re.compile(
    r"^SEARCH query_len=(?P<query_len>\d+) results=(?P<results>\d+) "
    r"db_ready_ms=[\d.]+ index_ms=[\d.]+ query_ms=[\d.]+ process_ms=[\d.]+ total_ms=[\d.]+$"
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(Starlette(routes=ROUTES, debug=True, exception_handlers={404: not_found}))


@pytest.mark.parametrize(("query", "expected_results"), [("apple", 2), ("nothingmatcheshere", 0)])
def test_search_emits_one_timing_line(  # noqa: PLR0917
    tmp_path, capsys, client, mock_user_session, query, expected_results
):
    yak_dir = tmp_path / "yaks"
    yak_dir.mkdir()
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    (yak_dir / "file1.dj").write_text("apple banana")
    (yak_dir / "file2.dj").write_text("apple cherry")

    with patch.dict("os.environ", {"YAK_SHEARS_DIR": str(yak_dir), "SEARCH_DB_DIR": str(db_dir)}):
        response = client.get(f"/search?query={query}")
        close_search_db()

    assert response.status_code == HTTPStatus.OK
    timing_lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith("SEARCH ")]
    assert len(timing_lines) == 1

    match = SEARCH_LINE_RE.match(timing_lines[0])
    assert match, timing_lines[0]
    assert int(match["query_len"]) == len(query)
    assert int(match["results"]) == expected_results


def test_stage_timer_reports_stages_in_completion_order():
    timer = StageTimer()
    with timer.stage("first"):
        pass
    with timer.stage("second"):
        pass

    line = timer.format_line("SEARCH", query_len=3)
    assert re.fullmatch(r"SEARCH query_len=3 first_ms=[\d.]+ second_ms=[\d.]+ total_ms=[\d.]+", line)
