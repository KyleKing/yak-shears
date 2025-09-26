import argparse
from unittest.mock import patch

import pytest

from yak_shears.auth.models import Password
from yak_shears.auth.storage import create_user
from yak_shears.cli import create_user_command, delete_user_command, list_users_command, main

from .conftest import SAMPLE_USER_EMAIL

ERROR_CODE = 2
"""Argparse exits with 2 for invalid command."""


def run_create_user_command(args, getpass_side_effect, expect_success=True):
    """Helper to run create_user_command with mocked inputs."""
    with patch("yak_shears.cli.getpass.getpass") as mock_getpass:
        mock_getpass.side_effect = getpass_side_effect
        with patch("yak_shears.cli.log") as mock_log:
            if expect_success:
                create_user_command(args)
                logged_messages = [call.args[0] for call in mock_log.call_args_list]
                return logged_messages
            else:
                with pytest.raises(SystemExit) as excinfo:
                    create_user_command(args)
                assert excinfo.value.code == 1
                logged_messages = [call.args[0] for call in mock_log.call_args_list]
                return logged_messages


@pytest.mark.parametrize(
    ("email", "display_name", "getpass_side_effect", "expected_messages"),
    [
        (
            "newuser@example.com",
            "Test User",
            ["secure123", "secure123"],
            ["Successfully created user: newuser@example.com (Test User)"],
        ),
        (
            "newuser2@example.com",
            None,
            ["secure123", "secure123"],
            ["Successfully created user: newuser2@example.com (newuser2@example.com)"],
        ),
        ("newuser3@example.com", "Test User", [""], ["Password cannot be empty"]),
        ("newuser4@example.com", "Test User", ["secure123", "different123"], ["Passwords do not match"]),
        (SAMPLE_USER_EMAIL, "Another User", ["secure123", "secure123"], ["already exists"]),
    ],
)
def test_create_user_scenarios(
    temp_user_file, sample_user, email, display_name, getpass_side_effect, expected_messages
):
    """Test various create user scenarios."""
    args = argparse.Namespace(email=email, display_name=display_name)
    logged_messages = run_create_user_command(args, getpass_side_effect, "already exists" not in expected_messages)

    for msg in expected_messages:
        assert any(msg in logged_msg for logged_msg in logged_messages)


def run_list_users_command(temp_user_file, sample_user, user_count=0):
    """Helper to run list_users_command and return logged messages."""
    if user_count > 0:
        for i in range(1, user_count + 1):
            create_user(f"user{i}@example.com", f"User {i}", Password(f"password{i}"))

    args = argparse.Namespace()
    with patch("yak_shears.cli.log") as mock_log:
        list_users_command(args)
        logged_messages = [call.args[0] for call in mock_log.call_args_list]
        return logged_messages


@pytest.mark.parametrize(
    ("user_count", "expected_messages"),
    [
        (0, [SAMPLE_USER_EMAIL, "Found 1 user"]),  # sample_user fixture creates 1 user
        (1, [SAMPLE_USER_EMAIL, "Found 2 users"]),  # 1 from fixture + 1 added
        (
            3,
            ["Found 4 users", "user1@example.com", "user2@example.com", "user3@example.com"],
        ),  # 1 from fixture + 3 added
    ],
)
def test_list_users_scenarios(temp_user_file, sample_user, user_count, expected_messages):
    """Test list users with different user counts."""
    logged_messages = run_list_users_command(temp_user_file, sample_user, user_count)

    for msg in expected_messages:
        assert any(msg in logged_msg for logged_msg in logged_messages)


def run_delete_user_command(args, input_value, expect_success=True):
    """Helper to run delete_user_command with mocked input."""
    with patch("builtins.input", return_value=input_value):
        with patch("yak_shears.cli.log") as mock_log:
            if expect_success:
                delete_user_command(args)
                logged_messages = [call.args[0] for call in mock_log.call_args_list]
                return logged_messages
            else:
                with pytest.raises(SystemExit) as excinfo:
                    delete_user_command(args)
                assert excinfo.value.code == 1
                logged_messages = [call.args[0] for call in mock_log.call_args_list]
                return logged_messages


@pytest.mark.parametrize(
    ("email", "input_value", "expected_messages", "expect_success"),
    [
        (SAMPLE_USER_EMAIL, "yes", ["Successfully deleted user: test@example.com"], True),
        ("nonexistent@example.com", "yes", ["not found"], False),
        (SAMPLE_USER_EMAIL, "no", ["Deletion cancelled"], True),
    ],
)
def test_delete_user_scenarios(sample_user, temp_user_file, email, input_value, expected_messages, expect_success):
    """Test delete user scenarios."""
    args = argparse.Namespace(email=email)
    logged_messages = run_delete_user_command(args, input_value, expect_success)

    for msg in expected_messages:
        assert any(msg in logged_msg for logged_msg in logged_messages)


def test_main_no_command(capsys):
    with patch("sys.argv", ["yak-shears-users"]):
        with pytest.raises(SystemExit) as excinfo:
            main()

        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert "usage:" in captured.out


def test_main_create_command(temp_user_file):
    test_args = ["yak-shears-users", "create", "test@example.com", "--display-name", "Test User"]

    with patch("sys.argv", test_args), patch("yak_shears.cli.getpass.getpass") as mock_getpass:
        mock_getpass.side_effect = ["secure123", "secure123"]

        with patch("yak_shears.cli.log") as mock_log:
            main()

        logged_messages = [call.args[0] for call in mock_log.call_args_list]
        assert any("Successfully created user" in msg for msg in logged_messages)


def test_main_list_command(temp_user_file):
    test_args = ["yak-shears-users", "list"]

    with patch("sys.argv", test_args):
        with patch("yak_shears.cli.log") as mock_log:
            main()

        logged_messages = [call.args[0] for call in mock_log.call_args_list]
        assert any("No users found" in msg for msg in logged_messages)


def test_main_delete_command(sample_user):
    test_args = ["yak-shears-users", "delete", SAMPLE_USER_EMAIL]

    with patch("sys.argv", test_args), patch("builtins.input", return_value="yes"):
        with patch("yak_shears.cli.log") as mock_log:
            main()

        logged_messages = [call.args[0] for call in mock_log.call_args_list]
        assert any("Successfully deleted user" in msg for msg in logged_messages)


def test_main_help_command(capsys):
    test_args = ["yak-shears-users", "--help"]

    with patch("sys.argv", test_args):
        with pytest.raises(SystemExit) as excinfo:
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

    with patch("sys.argv", test_args):
        with pytest.raises(SystemExit) as excinfo:
            main()

        assert excinfo.value.code == ERROR_CODE
        captured = capsys.readouterr()
        assert "invalid choice" in captured.err


def test_create_parser_optional_display_name(temp_user_file):
    test_args = ["yak-shears-users", "create", "test@example.com"]

    with patch("sys.argv", test_args), patch("yak_shears.cli.getpass.getpass") as mock_getpass:
        mock_getpass.side_effect = ["secure123", "secure123"]

        with patch("yak_shears.cli.log"):
            main()


def test_list_parser_no_args(temp_user_file):
    test_args = ["yak-shears-users", "list"]

    with patch("sys.argv", test_args), patch("yak_shears.cli.log"):
        main()  # Should not raise an exception
