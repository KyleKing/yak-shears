from collections.abc import Callable
from contextlib import contextmanager
from typing import Any
from unittest.mock import patch

import pytest

from yak_shears._auth.models import Password
from yak_shears._auth.storage import create_user
from yak_shears.cli import main

from .conftest import SAMPLE_USER_EMAIL

ERROR_CODE = 2
"""Argparse exits with 2 for invalid command."""

LOG_IMPORT = "yak_shears.cli.log"
"""Import path for log function."""


@contextmanager
def mock_getpass(
    *,
    password: str = "secure123",  # noqa: S107
    confirm_pass: str = "secure123",  # noqa: S107
    return_value: str = "yes",
):
    """Mock Python getpass module."""
    with patch("getpass.getpass") as mock:
        mock.side_effect = [password, confirm_pass]
        mock.return_value = return_value
        yield


def assert_logged_messages(mock_log, expected_messages: list[str | Callable[[str], bool]]) -> None:
    """Assert that mock_log was called with the expected messages or patterns."""
    mock_log.assert_called()
    logs = [call.args[0] for call in mock_log.call_args_list]
    for expected in expected_messages:
        if isinstance(expected, str):
            assert any(expected in msg for msg in logs), f"Expected substring '{expected}' not found in {logs}"
        else:
            assert any(expected(msg) for msg in logs), f"No message matched the predicate in {logs}"


@pytest.mark.parametrize(
    ("email", "name"),
    [
        ("test@example.com", "Test User"),
        ("test@example.com", None),
    ],
)
def test_create_user(temp_user_file, email, name):
    test_args = ["yak-shears-users", "create", email, *(["--display-name", name] if name else [])]

    with patch("sys.argv", test_args), mock_getpass(), patch(LOG_IMPORT) as mock_log:
        main()

    assert_logged_messages(mock_log, [f"Successfully created user: {email} ({name or email})"])


@pytest.mark.parametrize(
    ("password", "confirm_pass", "expected"),
    [
        ("secure123", "different123", ["Passwords do not match"]),
        ("", "", ["Password cannot be empty"]),
    ],
)
def test_create_user_errors(temp_user_file, password, confirm_pass, expected):
    test_args = ["yak-shears-users", "create", "test@example.com"]

    with (
        patch("sys.argv", test_args),
        mock_getpass(password=password, confirm_pass=confirm_pass),
        patch(LOG_IMPORT) as mock_log,
        pytest.raises(SystemExit) as excinfo,
    ):
        main()

    assert excinfo.value.code == 1
    assert_logged_messages(mock_log, expected)


def test_create_duplicate_user(sample_user):
    test_args = ["yak-shears-users", "create", SAMPLE_USER_EMAIL, "--display-name", "Another User"]

    with patch("sys.argv", test_args), patch(LOG_IMPORT) as mock_log, pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 1
    assert_logged_messages(mock_log, [lambda msg: "already exists" in msg])


@pytest.mark.parametrize("count", [0, 1, 3])
def test_list_users(temp_user_file, count):
    test_args = ["yak-shears-users", "list"]
    expected: Any = [f"Found {count} {'user' if count == 1 else 'users'}" if count else "No users found"]
    for idx in range(1, count + 1):
        email = f"user{idx}@example.com"
        create_user(email, f"User {idx}", Password(f"password{idx}"))
        expected.append(lambda msg, email=email: email in msg)

    with patch("sys.argv", test_args), patch(LOG_IMPORT) as mock_log:
        main()

    assert_logged_messages(mock_log, expected)


def test_delete_existing_user(sample_user):
    test_args = ["yak-shears-users", "delete", SAMPLE_USER_EMAIL]

    with patch("sys.argv", test_args), patch("builtins.input", return_value="yes"), patch(LOG_IMPORT) as mock_log:
        main()

    assert_logged_messages(mock_log, ["Successfully deleted user: test@example.com"])


def test_delete_nonexistent_user(temp_user_file):
    test_args = ["yak-shears-users", "delete", "nonexistent@example.com"]

    with patch("sys.argv", test_args), patch(LOG_IMPORT) as mock_log, pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 1
    assert_logged_messages(mock_log, [lambda msg: "not found" in msg])


def test_delete_user_cancelled(sample_user):
    test_args = ["yak-shears-users", "delete", SAMPLE_USER_EMAIL]

    with patch("sys.argv", test_args), patch("builtins.input", return_value="no"), patch(LOG_IMPORT) as mock_log:
        main()

    assert_logged_messages(mock_log, ["Deletion cancelled"])


def test_help_command(capsys):
    test_args = ["yak-shears-users", "--help"]

    with patch("sys.argv", test_args), pytest.raises(SystemExit) as excinfo:
        main()

    # argparse exits with 0 for help
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "Manage Yak Shears users" in captured.out
    assert "create" in captured.out
    assert "list" in captured.out
    assert "delete" in captured.out


def test_no_command(capsys):
    args = ["yak-shears-users"]

    with patch("sys.argv", args), pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "usage:" in captured.out


def test_main_invalid_command(capsys):
    test_args = ["yak-shears-users", "invalid"]

    with patch("sys.argv", test_args), pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == ERROR_CODE
    captured = capsys.readouterr()
    assert "invalid choice" in captured.err
