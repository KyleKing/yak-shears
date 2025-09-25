import argparse
from unittest.mock import patch

import pytest

from yak_shears.auth.models import Password
from yak_shears.auth.storage import create_user
from yak_shears.cli import create_user_command, delete_user_command, list_users_command, main

from .conftest import SAMPLE_USER_EMAIL

ERROR_CODE = 2
"""Argparse exits with 2 for invalid command."""


def test_create_user_success(temp_user_file):
    args = argparse.Namespace(email="test@example.com", display_name="Test User")

    with patch("yak_shears.cli.getpass.getpass") as mock_getpass:
        mock_getpass.side_effect = ["secure123", "secure123"]  # password and confirmation

        with patch("yak_shears.cli.log") as mock_log:
            create_user_command(args)

        mock_log.assert_called()
        logged_messages = [call.args[0] for call in mock_log.call_args_list]
        assert any("Successfully created user: test@example.com" in msg for msg in logged_messages)
        assert any("Test User" in msg for msg in logged_messages)


def test_create_user_no_display_name(temp_user_file):
    args = argparse.Namespace(email="test@example.com", display_name=None)

    with patch("yak_shears.cli.getpass.getpass") as mock_getpass:
        mock_getpass.side_effect = ["secure123", "secure123"]

        with patch("yak_shears.cli.log") as mock_log:
            create_user_command(args)

        logged_messages = [call.args[0] for call in mock_log.call_args_list]
        assert any("Successfully created user: test@example.com" in msg for msg in logged_messages)


def test_create_user_empty_password(temp_user_file):
    args = argparse.Namespace(email="test@example.com", display_name="Test User")

    with patch("yak_shears.cli.getpass.getpass") as mock_getpass:
        mock_getpass.return_value = ""

        with patch("yak_shears.cli.log") as mock_log:
            with pytest.raises(SystemExit) as excinfo:
                create_user_command(args)

            assert excinfo.value.code == 1
            logged_messages = [call.args[0] for call in mock_log.call_args_list]
            assert any("Password cannot be empty" in msg for msg in logged_messages)


def test_create_user_password_mismatch(temp_user_file):
    args = argparse.Namespace(email="test@example.com", display_name="Test User")

    with patch("yak_shears.cli.getpass.getpass") as mock_getpass:
        mock_getpass.side_effect = ["secure123", "different123"]

        with patch("yak_shears.cli.log") as mock_log:
            with pytest.raises(SystemExit) as excinfo:
                create_user_command(args)

            assert excinfo.value.code == 1
            logged_messages = [call.args[0] for call in mock_log.call_args_list]
            assert any("Passwords do not match" in msg for msg in logged_messages)


def test_create_duplicate_user(sample_user):
    args = argparse.Namespace(email=SAMPLE_USER_EMAIL, display_name="Another User")

    with patch("yak_shears.cli.log") as mock_log:
        with pytest.raises(SystemExit) as excinfo:
            create_user_command(args)

        assert excinfo.value.code == 1
        logged_messages = [call.args[0] for call in mock_log.call_args_list]
        assert any("already exists" in msg for msg in logged_messages)


def test_list_empty_users(temp_user_file):
    args = argparse.Namespace()

    with patch("yak_shears.cli.log") as mock_log:
        list_users_command(args)

    logged_messages = [call.args[0] for call in mock_log.call_args_list]
    assert any("No users found" in msg for msg in logged_messages)


def test_list_single_user(sample_user):
    args = argparse.Namespace()

    with patch("yak_shears.cli.log") as mock_log:
        list_users_command(args)

    logged_messages = [call.args[0] for call in mock_log.call_args_list]
    assert any(SAMPLE_USER_EMAIL in msg for msg in logged_messages)
    assert any("Found 1 users" in msg for msg in logged_messages)


def test_list_multiple_users(temp_user_file):
    create_user("user1@example.com", "User 1", Password("password1"))
    create_user("user2@example.com", "User 2", Password("password2"))
    create_user("user3@example.com", "User 3", Password("password3"))

    args = argparse.Namespace()

    with patch("yak_shears.cli.log") as mock_log:
        list_users_command(args)

    logged_messages = [call.args[0] for call in mock_log.call_args_list]
    assert any("Found 3 users" in msg for msg in logged_messages)
    assert any("user1@example.com" in msg for msg in logged_messages)
    assert any("user2@example.com" in msg for msg in logged_messages)
    assert any("user3@example.com" in msg for msg in logged_messages)


def test_delete_existing_user(sample_user):
    args = argparse.Namespace(email=SAMPLE_USER_EMAIL)

    with patch("builtins.input", return_value="yes"):
        with patch("yak_shears.cli.log") as mock_log:
            delete_user_command(args)

        logged_messages = [call.args[0] for call in mock_log.call_args_list]
        assert any("Successfully deleted user: test@example.com" in msg for msg in logged_messages)


def test_delete_nonexistent_user(temp_user_file):
    args = argparse.Namespace(email="nonexistent@example.com")

    with patch("yak_shears.cli.log") as mock_log:
        with pytest.raises(SystemExit) as excinfo:
            delete_user_command(args)

        assert excinfo.value.code == 1
        logged_messages = [call.args[0] for call in mock_log.call_args_list]
        assert any("not found" in msg for msg in logged_messages)


def test_delete_user_cancelled(sample_user):
    args = argparse.Namespace(email=SAMPLE_USER_EMAIL)

    with patch("builtins.input", return_value="no"):
        with patch("yak_shears.cli.log") as mock_log:
            delete_user_command(args)

        logged_messages = [call.args[0] for call in mock_log.call_args_list]
        assert any("Deletion cancelled" in msg for msg in logged_messages)


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


def test_full_user_lifecycle(temp_user_file):
    create_args = ["yak-shears-users", "create", "test@example.com", "--display-name", "Test User"]
    with patch("sys.argv", create_args), patch("yak_shears.cli.getpass.getpass") as mock_getpass:
        mock_getpass.side_effect = ["secure123", "secure123"]
        main()

    list_args = ["yak-shears-users", "list"]
    with patch("sys.argv", list_args):
        with patch("yak_shears.cli.log") as mock_log:
            main()

        logged_messages = [call.args[0] for call in mock_log.call_args_list]
        assert any("test@example.com" in msg for msg in logged_messages)

    delete_args = ["yak-shears-users", "delete", "test@example.com"]
    with patch("sys.argv", delete_args), patch("builtins.input", return_value="yes"):
        main()

    with patch("sys.argv", list_args):
        with patch("yak_shears.cli.log") as mock_log:
            main()

        logged_messages = [call.args[0] for call in mock_log.call_args_list]
        assert any("No users found" in msg for msg in logged_messages)


def test_create_multiple_users_and_list(temp_user_file):
    users = [
        ("user1@example.com", "User One"),
        ("user2@example.com", "User Two"),
        ("user3@example.com", "User Three"),
    ]
    for email, display_name in users:
        create_args = ["yak-shears-users", "create", email, "--display-name", display_name]
        with patch("sys.argv", create_args), patch("yak_shears.cli.getpass.getpass") as mock_getpass:
            mock_getpass.side_effect = ["password123", "password123"]
            main()

    list_args = ["yak-shears-users", "list"]
    with patch("sys.argv", list_args):
        with patch("yak_shears.cli.log") as mock_log:
            main()

        logged_messages = [call.args[0] for call in mock_log.call_args_list]
        assert any("Found 3 users" in msg for msg in logged_messages)
        for email, display_name in users:
            assert any(email in msg for msg in logged_messages)
            assert any(display_name in msg for msg in logged_messages)


def test_unicode_user_data(temp_user_file):
    email = "тест@пример.рф"
    display_name = "测试用户"

    create_args = ["yak-shears-users", "create", email, "--display-name", display_name]
    with patch("sys.argv", create_args), patch("yak_shears.cli.getpass.getpass") as mock_getpass:
        mock_getpass.side_effect = ["пароль123", "пароль123"]  # noqa: RUF001
        main()

    # List should show Unicode correctly
    list_args = ["yak-shears-users", "list"]
    with patch("sys.argv", list_args):
        with patch("yak_shears.cli.log") as mock_log:
            main()

        logged_messages = [call.args[0] for call in mock_log.call_args_list]
        assert any(email in msg for msg in logged_messages)
        assert any(display_name in msg for msg in logged_messages)


def test_create_parser_required_args(capsys):
    test_args = ["yak-shears-users", "create"]

    with patch("sys.argv", test_args):
        with pytest.raises(SystemExit) as excinfo:
            main()

        assert excinfo.value.code == ERROR_CODE
        captured = capsys.readouterr()
        assert "required" in captured.err


def test_create_parser_optional_display_name(temp_user_file):
    test_args = ["yak-shears-users", "create", "test@example.com"]

    with patch("sys.argv", test_args), patch("yak_shears.cli.getpass.getpass") as mock_getpass:
        mock_getpass.side_effect = ["secure123", "secure123"]

        with patch("yak_shears.cli.log"):
            main()


def test_delete_parser_required_args(capsys):
    test_args = ["yak-shears-users", "delete"]

    with patch("sys.argv", test_args):
        with pytest.raises(SystemExit) as excinfo:
            main()

        assert excinfo.value.code == ERROR_CODE
        captured = capsys.readouterr()
        assert "required" in captured.err


def test_list_parser_no_args(temp_user_file):
    test_args = ["yak-shears-users", "list"]

    with patch("sys.argv", test_args), patch("yak_shears.cli.log"):
        main()  # Should not raise an exception
