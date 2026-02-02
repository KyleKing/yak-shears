"""Tests for server CLI argument parsing."""

from unittest.mock import patch

import pytest

from yak_shears.server._routes import cli


@pytest.mark.parametrize(
    ("args", "expected_start_args"),
    [
        (
            [],
            {"host": "localhost", "port": 8080, "reload": False, "no_auth": False, "search_db_dir": None},
        ),
        (
            ["--host", "0.0.0.0"],
            {"host": "0.0.0.0", "port": 8080, "reload": False, "no_auth": False, "search_db_dir": None},
        ),
        (
            ["--port", "3000"],
            {"host": "localhost", "port": 3000, "reload": False, "no_auth": False, "search_db_dir": None},
        ),
        (
            ["--reload"],
            {"host": "localhost", "port": 8080, "reload": True, "no_auth": False, "search_db_dir": None},
        ),
        (
            ["--reload", "--no-auth"],
            {"host": "localhost", "port": 8080, "reload": True, "no_auth": True, "search_db_dir": None},
        ),
        (
            ["--search-db-dir", "/custom/db"],
            {"host": "localhost", "port": 8080, "reload": False, "no_auth": False, "search_db_dir": "/custom/db"},
        ),
        (
            ["--host", "127.0.0.1", "--port", "9000", "--reload"],
            {"host": "127.0.0.1", "port": 9000, "reload": True, "no_auth": False, "search_db_dir": None},
        ),
    ],
    ids=[
        "defaults",
        "custom_host",
        "custom_port",
        "reload_enabled",
        "reload_with_no_auth",
        "custom_search_db",
        "multiple_args",
    ],
)
def test_cli_argument_parsing(args, expected_start_args):
    """Test that CLI arguments are correctly parsed and passed to start()."""
    test_args = ["serve", *args]

    with (
        patch("sys.argv", test_args),
        patch("yak_shears.server._routes.start") as mock_start,
    ):
        cli()

    mock_start.assert_called_once_with(**expected_start_args)


def test_cli_help_displays_usage(capsys):
    """Test that --help displays usage information."""
    test_args = ["serve", "--help"]

    with patch("sys.argv", test_args), pytest.raises(SystemExit) as excinfo:
        cli()

    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "Run the Yak Shears development server" in captured.out
    assert "--host" in captured.out
    assert "--port" in captured.out
    assert "--reload" in captured.out
    assert "--no-auth" in captured.out
    assert "--search-db-dir" in captured.out
