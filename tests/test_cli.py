"""Tests for the CLI user management functionality."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from yak_shears import cli
from yak_shears.cli import create_user_command, delete_user_command, list_users_command


@pytest.fixture
def temp_user_file():
    """Create a temporary user file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_path = Path(f.name)
        f.write('{"users": {}, "email_to_user_id": {}, "sessions": {}}')

    # Patch the storage file path
    with patch("yak_shears.auth.storage._USER_DATA_PATH", temp_path):
        # Reset the in-memory storage
        with patch("yak_shears.auth.storage._users", {}):
            with patch("yak_shears.auth.storage._email_to_user_id", {}):
                with patch("yak_shears.auth.storage._session_store", {}):
                    yield temp_path

    # Clean up
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def cli_runner():
    """Create a CLI runner for testing."""
    from click.testing import CliRunner

    return CliRunner()


class TestCreateCommand:
    """Test the create user CLI command."""

    def test_create_user_interactive(self, cli_runner, temp_user_file):
        """Test creating a user interactively."""
        # Mock getpass to provide password
        with patch("yak_shears.cli.getpass.getpass") as mock_getpass:
            mock_getpass.return_value = "secure123"

            result = cli_runner.invoke(create_user_command, ["test@example.com", "--display-name", "Test User"])

        assert result.exit_code == 0
        assert "User created successfully" in result.output
        assert "test@example.com" in result.output

    def test_create_user_with_password_option(self, cli_runner, temp_user_file):
        """Test creating a user with password option."""
        result = cli_runner.invoke(
            create_user_command, ["test@example.com", "--display-name", "Test User", "--password", "secure123"]
        )

        assert result.exit_code == 0
        assert "User created successfully" in result.output
        assert "test@example.com" in result.output

    def test_create_user_without_display_name(self, cli_runner, temp_user_file):
        """Test creating a user without display name (should use email)."""
        with patch("yak_shears.cli.getpass.getpass") as mock_getpass:
            mock_getpass.return_value = "secure123"

            result = cli_runner.invoke(create_user_command, ["test@example.com"])

        assert result.exit_code == 0
        assert "User created successfully" in result.output

    def test_create_duplicate_user(self, cli_runner, temp_user_file):
        """Test creating a duplicate user."""
        # Create first user
        with patch("yak_shears.cli.getpass.getpass") as mock_getpass:
            mock_getpass.return_value = "secure123"

            result1 = cli_runner.invoke(create_user_command, ["test@example.com", "--display-name", "Test User"])
            assert result1.exit_code == 0

            # Try to create duplicate
            result2 = cli_runner.invoke(create_user_command, ["test@example.com", "--display-name", "Another User"])

        assert result2.exit_code == 1
        assert "Error: User with email" in result2.output
        assert "already exists" in result2.output

    def test_create_user_empty_password(self, cli_runner, temp_user_file):
        """Test creating a user with empty password."""
        with patch("yak_shears.cli.getpass.getpass") as mock_getpass:
            mock_getpass.return_value = ""

            result = cli_runner.invoke(create_user_command, ["test@example.com", "--display-name", "Test User"])

        assert result.exit_code == 1
        assert "Password cannot be empty" in result.output

    def test_create_user_password_confirmation_mismatch(self, cli_runner, temp_user_file):
        """Test creating a user with password confirmation mismatch."""
        with patch("yak_shears.cli.getpass.getpass") as mock_getpass:
            # First call returns password, second returns different confirmation
            mock_getpass.side_effect = ["secure123", "different123"]

            result = cli_runner.invoke(create_user_command, ["test@example.com", "--display-name", "Test User"])

        assert result.exit_code == 1
        assert "Passwords do not match" in result.output

    def test_create_user_password_confirmation_success(self, cli_runner, temp_user_file):
        """Test creating a user with matching password confirmation."""
        with patch("yak_shears.cli.getpass.getpass") as mock_getpass:
            # Both calls return the same password
            mock_getpass.side_effect = ["secure123", "secure123"]

            result = cli_runner.invoke(create_user_command, ["test@example.com", "--display-name", "Test User"])

        assert result.exit_code == 0
        assert "User created successfully" in result.output


class TestListCommand:
    """Test the list users CLI command."""

    def test_list_empty_users(self, cli_runner, temp_user_file):
        """Test listing when no users exist."""
        result = cli_runner.invoke(list_users_command)

        assert result.exit_code == 0
        assert "No users found" in result.output

    def test_list_single_user(self, cli_runner, temp_user_file):
        """Test listing with a single user."""
        # Create a user first
        from yak_shears.auth.storage import create_user

        create_user("test@example.com", "Test User", "password")

        result = cli_runner.invoke(list_users_command)

        assert result.exit_code == 0
        assert "test@example.com" in result.output
        assert "Test User" in result.output

    def test_list_multiple_users(self, cli_runner, temp_user_file):
        """Test listing multiple users."""
        # Create multiple users
        from yak_shears.auth.storage import create_user

        create_user("user1@example.com", "User 1", "password1")
        create_user("user2@example.com", "User 2", "password2")
        create_user("user3@example.com", "User 3", "password3")

        result = cli_runner.invoke(list_users_command)

        assert result.exit_code == 0
        assert "user1@example.com" in result.output
        assert "user2@example.com" in result.output
        assert "user3@example.com" in result.output
        assert "User 1" in result.output
        assert "User 2" in result.output
        assert "User 3" in result.output

    def test_list_shows_creation_date(self, cli_runner, temp_user_file):
        """Test that list shows creation date."""
        from yak_shears.auth.storage import create_user

        create_user("test@example.com", "Test User", "password")

        result = cli_runner.invoke(list_users_command)

        assert result.exit_code == 0
        # Should contain a date (basic check for ISO format)
        assert "T" in result.output and ":" in result.output


class TestDeleteCommand:
    """Test the delete user CLI command."""

    def test_delete_existing_user(self, cli_runner, temp_user_file):
        """Test deleting an existing user."""
        # Create a user first
        from yak_shears.auth.storage import create_user

        create_user("test@example.com", "Test User", "password")

        result = cli_runner.invoke(delete_user_command, ["test@example.com"])

        assert result.exit_code == 0
        assert "User deleted successfully" in result.output

    def test_delete_nonexistent_user(self, cli_runner, temp_user_file):
        """Test deleting a non-existent user."""
        result = cli_runner.invoke(delete_user_command, ["nonexistent@example.com"])

        assert result.exit_code == 1
        assert "User not found" in result.output

    def test_delete_user_confirmation_yes(self, cli_runner, temp_user_file):
        """Test deleting user with confirmation (yes)."""
        # Create a user first
        from yak_shears.auth.storage import create_user

        create_user("test@example.com", "Test User", "password")

        # Mock input to confirm deletion
        result = cli_runner.invoke(delete_user_command, ["test@example.com"], input="y\n")

        assert result.exit_code == 0
        assert "User deleted successfully" in result.output

    def test_delete_user_confirmation_no(self, cli_runner, temp_user_file):
        """Test deleting user with confirmation (no)."""
        # Create a user first
        from yak_shears.auth.storage import create_user

        create_user("test@example.com", "Test User", "password")

        # Mock input to cancel deletion
        result = cli_runner.invoke(delete_user_command, ["test@example.com"], input="n\n")

        assert result.exit_code == 0
        assert "Deletion cancelled" in result.output

    def test_delete_user_force(self, cli_runner, temp_user_file):
        """Test deleting user with force flag."""
        # Create a user first
        from yak_shears.auth.storage import create_user

        create_user("test@example.com", "Test User", "password")

        result = cli_runner.invoke(delete_user_command, ["test@example.com", "--force"])

        assert result.exit_code == 0
        assert "User deleted successfully" in result.output
        # Should not prompt for confirmation
        assert "Are you sure" not in result.output


class TestMainCLI:
    """Test the main CLI interface."""

    def test_cli_help(self, cli_runner):
        """Test CLI help output."""
        result = cli_runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "create" in result.output
        assert "list" in result.output
        assert "delete" in result.output

    def test_cli_create_subcommand(self, cli_runner, temp_user_file):
        """Test CLI create subcommand."""
        with patch("yak_shears.cli.getpass.getpass") as mock_getpass:
            mock_getpass.return_value = "secure123"

            result = cli_runner.invoke(cli, ["create", "test@example.com", "--display-name", "Test User"])

        assert result.exit_code == 0
        assert "User created successfully" in result.output

    def test_cli_list_subcommand(self, cli_runner, temp_user_file):
        """Test CLI list subcommand."""
        result = cli_runner.invoke(cli, ["list"])

        assert result.exit_code == 0
        assert "No users found" in result.output

    def test_cli_delete_subcommand(self, cli_runner, temp_user_file):
        """Test CLI delete subcommand."""
        result = cli_runner.invoke(cli, ["delete", "nonexistent@example.com"])

        assert result.exit_code == 1
        assert "User not found" in result.output

    def test_cli_invalid_subcommand(self, cli_runner):
        """Test CLI with invalid subcommand."""
        result = cli_runner.invoke(cli, ["invalid"])

        assert result.exit_code != 0
        assert "No such command" in result.output


class TestCLIIntegration:
    """Test CLI integration scenarios."""

    def test_full_user_lifecycle(self, cli_runner, temp_user_file):
        """Test complete user lifecycle: create, list, delete."""
        # Create user
        with patch("yak_shears.cli.getpass.getpass") as mock_getpass:
            mock_getpass.return_value = "secure123"

            create_result = cli_runner.invoke(cli, ["create", "test@example.com", "--display-name", "Test User"])
            assert create_result.exit_code == 0

        # List users
        list_result = cli_runner.invoke(cli, ["list"])
        assert list_result.exit_code == 0
        assert "test@example.com" in list_result.output

        # Delete user
        delete_result = cli_runner.invoke(cli, ["delete", "test@example.com", "--force"])
        assert delete_result.exit_code == 0

        # Verify user is gone
        final_list_result = cli_runner.invoke(cli, ["list"])
        assert final_list_result.exit_code == 0
        assert "No users found" in final_list_result.output

    def test_create_multiple_users_and_list(self, cli_runner, temp_user_file):
        """Test creating multiple users and listing them."""
        users = [
            ("user1@example.com", "User One"),
            ("user2@example.com", "User Two"),
            ("user3@example.com", "User Three"),
        ]

        # Create all users
        for email, display_name in users:
            with patch("yak_shears.cli.getpass.getpass") as mock_getpass:
                mock_getpass.return_value = "password123"

                result = cli_runner.invoke(cli, ["create", email, "--display-name", display_name])
                assert result.exit_code == 0

        # List all users
        list_result = cli_runner.invoke(cli, ["list"])
        assert list_result.exit_code == 0

        for email, display_name in users:
            assert email in list_result.output
            assert display_name in list_result.output

    def test_error_handling_in_cli(self, cli_runner, temp_user_file):
        """Test error handling in CLI commands."""
        # Test creating user with invalid data
        with patch("yak_shears.cli.getpass.getpass") as mock_getpass:
            mock_getpass.return_value = ""  # Empty password

            result = cli_runner.invoke(cli, ["create", "test@example.com", "--display-name", "Test User"])
            assert result.exit_code == 1
            assert "Password cannot be empty" in result.output

    def test_cli_with_unicode_data(self, cli_runner, temp_user_file):
        """Test CLI with Unicode characters."""
        email = "тест@пример.рф"
        display_name = "测试用户"

        with patch("yak_shears.cli.getpass.getpass") as mock_getpass:
            mock_getpass.return_value = "пароль123"

            create_result = cli_runner.invoke(cli, ["create", email, "--display-name", display_name])
            assert create_result.exit_code == 0

        # List should show Unicode correctly
        list_result = cli_runner.invoke(cli, ["list"])
        assert list_result.exit_code == 0
        assert email in list_result.output
        assert display_name in list_result.output
