import argparse
from io import StringIO
from unittest.mock import patch

import pytest

from yak_shears.auth.models import Password
from yak_shears.auth.storage import create_user
from yak_shears.cli import create_user_command, delete_user_command, list_users_command, main

from .conftest import SAMPLE_USER_EMAIL

ERROR_CODE = 2
"""Argparse exits with 2 for invalid command."""


class TestCreateUserCommand:
    def test_create_user_success(self, temp_user_file):
        args = argparse.Namespace(email="test@example.com", display_name="Test User")

        with patch("yak_shears.cli.getpass.getpass") as mock_getpass:
            mock_getpass.side_effect = ["secure123", "secure123"]  # password and confirmation

            with patch("sys.stdout", new=StringIO()) as fake_stdout:
                create_user_command(args)

            output = fake_stdout.getvalue()
            assert "Successfully created user: test@example.com" in output
            assert "Test User" in output

    def test_create_user_no_display_name(self, temp_user_file):
        args = argparse.Namespace(email="test@example.com", display_name=None)

        with patch("yak_shears.cli.getpass.getpass") as mock_getpass:
            mock_getpass.side_effect = ["secure123", "secure123"]

            with patch("sys.stdout", new=StringIO()) as fake_stdout:
                create_user_command(args)

            output = fake_stdout.getvalue()
            assert "Successfully created user: test@example.com" in output

    def test_create_user_empty_password(self, temp_user_file):
        args = argparse.Namespace(email="test@example.com", display_name="Test User")

        with patch("yak_shears.cli.getpass.getpass") as mock_getpass:
            mock_getpass.return_value = ""

            with patch("sys.stderr", new=StringIO()) as fake_stderr:
                with pytest.raises(SystemExit) as excinfo:
                    create_user_command(args)

                assert excinfo.value.code == 1
                assert "Password cannot be empty" in fake_stderr.getvalue()

    def test_create_user_password_mismatch(self, temp_user_file):
        args = argparse.Namespace(email="test@example.com", display_name="Test User")

        with patch("yak_shears.cli.getpass.getpass") as mock_getpass:
            mock_getpass.side_effect = ["secure123", "different123"]

            with patch("sys.stderr", new=StringIO()) as fake_stderr:
                with pytest.raises(SystemExit) as excinfo:
                    create_user_command(args)

                assert excinfo.value.code == 1
                assert "Passwords do not match" in fake_stderr.getvalue()

    def test_create_duplicate_user(self, sample_user):
        args = argparse.Namespace(email=SAMPLE_USER_EMAIL, display_name="Another User")

        with patch("sys.stderr", new=StringIO()) as fake_stderr:
            with pytest.raises(SystemExit) as excinfo:
                create_user_command(args)

            assert excinfo.value.code == 1
            assert "already exists" in fake_stderr.getvalue()


class TestListUsersCommand:
    def test_list_empty_users(self, temp_user_file):
        args = argparse.Namespace()

        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            list_users_command(args)

        output = fake_stdout.getvalue()
        assert "No users found" in output

    def test_list_single_user(self, sample_user):
        args = argparse.Namespace()

        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            list_users_command(args)

        output = fake_stdout.getvalue()
        assert SAMPLE_USER_EMAIL in output
        assert "Found 1 users" in output

    def test_list_multiple_users(self, temp_user_file):
        create_user("user1@example.com", "User 1", Password("password1"))
        create_user("user2@example.com", "User 2", Password("password2"))
        create_user("user3@example.com", "User 3", Password("password3"))

        args = argparse.Namespace()

        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            list_users_command(args)

        output = fake_stdout.getvalue()
        assert "Found 3 users" in output
        assert "user1@example.com" in output
        assert "user2@example.com" in output
        assert "user3@example.com" in output


class TestDeleteUserCommand:
    def test_delete_existing_user(self, sample_user):
        args = argparse.Namespace(email=SAMPLE_USER_EMAIL)

        with patch("builtins.input", return_value="yes"):
            with patch("sys.stdout", new=StringIO()) as fake_stdout:
                delete_user_command(args)

            output = fake_stdout.getvalue()
            assert "Successfully deleted user: test@example.com" in output

    def test_delete_nonexistent_user(self, temp_user_file):
        args = argparse.Namespace(email="nonexistent@example.com")

        with patch("sys.stderr", new=StringIO()) as fake_stderr:
            with pytest.raises(SystemExit) as excinfo:
                delete_user_command(args)

            assert excinfo.value.code == 1
            assert "not found" in fake_stderr.getvalue()

    def test_delete_user_cancelled(self, sample_user):
        args = argparse.Namespace(email=SAMPLE_USER_EMAIL)

        with patch("builtins.input", return_value="no"):
            with patch("sys.stdout", new=StringIO()) as fake_stdout:
                delete_user_command(args)

            output = fake_stdout.getvalue()
            assert "Deletion cancelled" in output


class TestMainCLI:
    def test_main_no_command(self):
        with patch("sys.argv", ["yak-shears-users"]), patch("sys.stdout", new=StringIO()) as fake_stdout:
            with pytest.raises(SystemExit) as excinfo:
                main()

            assert excinfo.value.code == 1
            output = fake_stdout.getvalue()
            assert "usage:" in output

    def test_main_create_command(self, temp_user_file):
        test_args = ["yak-shears-users", "create", "test@example.com", "--display-name", "Test User"]

        with patch("sys.argv", test_args), patch("yak_shears.cli.getpass.getpass") as mock_getpass:
            mock_getpass.side_effect = ["secure123", "secure123"]

            with patch("sys.stdout", new=StringIO()) as fake_stdout:
                main()

            output = fake_stdout.getvalue()
            assert "Successfully created user" in output

    def test_main_list_command(self, temp_user_file):
        test_args = ["yak-shears-users", "list"]

        with patch("sys.argv", test_args):
            with patch("sys.stdout", new=StringIO()) as fake_stdout:
                main()

            output = fake_stdout.getvalue()
            assert "No users found" in output

    def test_main_delete_command(self, sample_user):
        test_args = ["yak-shears-users", "delete", SAMPLE_USER_EMAIL]

        with patch("sys.argv", test_args), patch("builtins.input", return_value="yes"):
            with patch("sys.stdout", new=StringIO()) as fake_stdout:
                main()

            output = fake_stdout.getvalue()
            assert "Successfully deleted user" in output

    def test_main_help_command(self):
        test_args = ["yak-shears-users", "--help"]

        with patch("sys.argv", test_args), patch("sys.stdout", new=StringIO()) as fake_stdout:
            with pytest.raises(SystemExit) as excinfo:
                main()

            # argparse exits with 0 for help
            assert excinfo.value.code == 0
            output = fake_stdout.getvalue()
            assert "Manage Yak Shears users" in output
            assert "create" in output
            assert "list" in output
            assert "delete" in output

    def test_main_invalid_command(self):
        test_args = ["yak-shears-users", "invalid"]

        with patch("sys.argv", test_args), patch("sys.stderr", new=StringIO()) as fake_stderr:
            with pytest.raises(SystemExit) as excinfo:
                main()

            assert excinfo.value.code == ERROR_CODE
            output = fake_stderr.getvalue()
            assert "invalid choice" in output


class TestCLIIntegration:
    def test_full_user_lifecycle(self, temp_user_file):
        create_args = ["yak-shears-users", "create", "test@example.com", "--display-name", "Test User"]
        with patch("sys.argv", create_args), patch("yak_shears.cli.getpass.getpass") as mock_getpass:
            mock_getpass.side_effect = ["secure123", "secure123"]
            main()

        list_args = ["yak-shears-users", "list"]
        with patch("sys.argv", list_args):
            with patch("sys.stdout", new=StringIO()) as fake_stdout:
                main()

            output = fake_stdout.getvalue()
            assert "test@example.com" in output

        delete_args = ["yak-shears-users", "delete", "test@example.com"]
        with patch("sys.argv", delete_args), patch("builtins.input", return_value="yes"):
            main()

        with patch("sys.argv", list_args):
            with patch("sys.stdout", new=StringIO()) as fake_stdout:
                main()

            output = fake_stdout.getvalue()
            assert "No users found" in output

    def test_create_multiple_users_and_list(self, temp_user_file):
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
            with patch("sys.stdout", new=StringIO()) as fake_stdout:
                main()

            output = fake_stdout.getvalue()
            assert "Found 3 users" in output
            for email, display_name in users:
                assert email in output
                assert display_name in output

    def test_unicode_user_data(self, temp_user_file):
        email = "тест@пример.рф"
        display_name = "测试用户"

        create_args = ["yak-shears-users", "create", email, "--display-name", display_name]
        with patch("sys.argv", create_args), patch("yak_shears.cli.getpass.getpass") as mock_getpass:
            mock_getpass.side_effect = ["пароль123", "пароль123"]  # noqa: RUF001
            main()

        # List should show Unicode correctly
        list_args = ["yak-shears-users", "list"]
        with patch("sys.argv", list_args):
            with patch("sys.stdout", new=StringIO()) as fake_stdout:
                main()

            output = fake_stdout.getvalue()
            assert email in output
            assert display_name in output


class TestArgumentParsing:
    def test_create_parser_required_args(self):
        test_args = ["yak-shears-users", "create"]

        with patch("sys.argv", test_args), patch("sys.stderr", new=StringIO()) as fake_stderr:
            with pytest.raises(SystemExit) as excinfo:
                main()

            assert excinfo.value.code == ERROR_CODE
            assert "required" in fake_stderr.getvalue()

    def test_create_parser_optional_display_name(self, temp_user_file):
        test_args = ["yak-shears-users", "create", "test@example.com"]

        with patch("sys.argv", test_args), patch("yak_shears.cli.getpass.getpass") as mock_getpass:
            mock_getpass.side_effect = ["secure123", "secure123"]

            with patch("sys.stdout", new=StringIO()):
                main()

    def test_delete_parser_required_args(self):
        test_args = ["yak-shears-users", "delete"]

        with patch("sys.argv", test_args), patch("sys.stderr", new=StringIO()) as fake_stderr:
            with pytest.raises(SystemExit) as excinfo:
                main()

            assert excinfo.value.code == ERROR_CODE
            assert "required" in fake_stderr.getvalue()

    def test_list_parser_no_args(self, temp_user_file):
        test_args = ["yak-shears-users", "list"]

        with patch("sys.argv", test_args), patch("sys.stdout", new=StringIO()):
            # Should not raise an exception
            main()
