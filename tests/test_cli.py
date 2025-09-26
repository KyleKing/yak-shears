import argparse
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from yak_shears.auth.models import Password
from yak_shears.auth.storage import create_user
from yak_shears.cli import create_user_command, delete_user_command, list_users_command, main

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


@pytest.mark.parametrize(
    ("email", "name"),
    [
        ("test@example.com", "Test User"),
        ("test@example.com", None),
    ],
)
def test_create_user(temp_user_file, email, name):
    args = argparse.Namespace(email=email, display_name=name)

    with mock_getpass(), patch(LOG_IMPORT) as mock_log:
        create_user_command(args)

    mock_log.assert_called()
    logs = [call.args[0] for call in mock_log.call_args_list]
    assert any(f"Successfully created user: {email} ({name or email})" == msg for msg in logs), logs
    assert any(msg.startswith("User ID: ") for msg in logs), logs


def test_create_user_empty_password(temp_user_file):
    args = argparse.Namespace(email="test@example.com", display_name="Test User")

    with (
        mock_getpass(password="", confirm_pass=""),
        patch(LOG_IMPORT) as mock_log,
        pytest.raises(SystemExit) as excinfo,
    ):
        create_user_command(args)

    assert excinfo.value.code == 1
    logs = [call.args[0] for call in mock_log.call_args_list]
    assert any("Password cannot be empty" in msg for msg in logs), logs


def test_create_user_password_mismatch(temp_user_file):
    args = argparse.Namespace(email="test@example.com", display_name="Test User")

    with (
        mock_getpass(confirm_pass="different123"),  # noqa: S106
        patch(LOG_IMPORT) as mock_log,
        pytest.raises(SystemExit) as excinfo,
    ):
        create_user_command(args)

    assert excinfo.value.code == 1
    logs = [call.args[0] for call in mock_log.call_args_list]
    assert any("Passwords do not match" in msg for msg in logs), logs


def test_create_duplicate_user(sample_user):
    args = argparse.Namespace(email=SAMPLE_USER_EMAIL, display_name="Another User")

    with patch(LOG_IMPORT) as mock_log, pytest.raises(SystemExit) as excinfo:
        create_user_command(args)

    assert excinfo.value.code == 1
    logs = [call.args[0] for call in mock_log.call_args_list]
    assert any("already exists" in msg for msg in logs), logs


def test_list_empty_users(temp_user_file):
    args = argparse.Namespace()

    with patch(LOG_IMPORT) as mock_log:
        list_users_command(args)

    logs = [call.args[0] for call in mock_log.call_args_list]
    assert any("No users found" in msg for msg in logs), logs


def test_list_single_user(sample_user):
    args = argparse.Namespace()

    with patch(LOG_IMPORT) as mock_log:
        list_users_command(args)

    logs = [call.args[0] for call in mock_log.call_args_list]
    assert any(SAMPLE_USER_EMAIL in msg for msg in logs), logs
    assert any("Found 1 users" in msg for msg in logs), logs


def test_list_multiple_users(temp_user_file):
    create_user("user1@example.com", "User 1", Password("password1"))
    create_user("user2@example.com", "User 2", Password("password2"))
    create_user("user3@example.com", "User 3", Password("password3"))

    args = argparse.Namespace()

    with patch(LOG_IMPORT) as mock_log:
        list_users_command(args)

    logs = [call.args[0] for call in mock_log.call_args_list]
    assert any("Found 3 users" in msg for msg in logs), logs
    assert any("user1@example.com" in msg for msg in logs), logs
    assert any("user2@example.com" in msg for msg in logs), logs
    assert any("user3@example.com" in msg for msg in logs), logs


def test_delete_existing_user(sample_user):
    args = argparse.Namespace(email=SAMPLE_USER_EMAIL)

    with patch("builtins.input", return_value="yes"), patch(LOG_IMPORT) as mock_log:
        delete_user_command(args)

    logs = [call.args[0] for call in mock_log.call_args_list]
    assert any("Successfully deleted user: test@example.com" in msg for msg in logs), logs


def test_delete_nonexistent_user(temp_user_file):
    args = argparse.Namespace(email="nonexistent@example.com")

    with patch(LOG_IMPORT) as mock_log, pytest.raises(SystemExit) as excinfo:
        delete_user_command(args)

    assert excinfo.value.code == 1
    logs = [call.args[0] for call in mock_log.call_args_list]
    assert any("not found" in msg for msg in logs), logs


def test_delete_user_cancelled(sample_user):
    args = argparse.Namespace(email=SAMPLE_USER_EMAIL)

    with patch("builtins.input", return_value="no"), patch(LOG_IMPORT) as mock_log:
        delete_user_command(args)

    logs = [call.args[0] for call in mock_log.call_args_list]
    assert any("Deletion cancelled" in msg for msg in logs), logs


def test_main_no_command(capsys):
    args = ["yak-shears-users"]

    with patch("sys.argv", args), pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "usage:" in captured.out


def test_main_create_command(temp_user_file):
    test_args = ["yak-shears-users", "create", "test@example.com", "--display-name", "Test User"]

    with patch("sys.argv", test_args), mock_getpass(), patch(LOG_IMPORT) as mock_log:
        main()

    logs = [call.args[0] for call in mock_log.call_args_list]
    assert any("Successfully created user" in msg for msg in logs), logs


def test_main_list_command(temp_user_file):
    test_args = ["yak-shears-users", "list"]

    with patch("sys.argv", test_args), patch(LOG_IMPORT) as mock_log:
        main()

    logs = [call.args[0] for call in mock_log.call_args_list]
    assert any("No users found" in msg for msg in logs), logs


def test_main_delete_command(sample_user):
    test_args = ["yak-shears-users", "delete", SAMPLE_USER_EMAIL]

    with (
        patch("sys.argv", test_args),
        patch("builtins.input", return_value="yes"),
        patch(LOG_IMPORT) as mock_log,
    ):
        main()

    logs = [call.args[0] for call in mock_log.call_args_list]
    assert any("Successfully deleted user" in msg for msg in logs), logs


def test_main_help_command(capsys):
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


def test_main_invalid_command(capsys):
    test_args = ["yak-shears-users", "invalid"]

    with patch("sys.argv", test_args), pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == ERROR_CODE
    captured = capsys.readouterr()
    assert "invalid choice" in captured.err


def test_create_parser_optional_display_name(temp_user_file):
    test_args = ["yak-shears-users", "create", "test@example.com"]

    with patch("sys.argv", test_args), mock_getpass(), patch(LOG_IMPORT):
        main()


def test_list_parser_no_args(temp_user_file):
    test_args = ["yak-shears-users", "list"]

    with patch("sys.argv", test_args), patch(LOG_IMPORT):
        main()  # Should not raise an exception
