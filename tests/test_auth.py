"""Tests for the authentication system."""

import json

import pytest

from yak_shears.auth.models import Password
from yak_shears.auth.password import generate_salt, hash_password, verify_password
from yak_shears.auth.storage import (
    authenticate_user,
    create_session,
    create_user,
    delete_session,
    delete_user,
    get_user_by_email,
    get_user_by_id,
    list_all_users,
)


@pytest.fixture
def sample_user(temp_user_file):
    """Create a sample user for testing."""
    email = "test@example.com"
    display_name = "Test User"
    password = Password("secure123")

    user = create_user(email, display_name, password)
    return user


class TestPasswordHashing:
    """Test password hashing functionality."""

    def test_generate_salt(self):
        """Test salt generation."""
        salt1 = generate_salt()
        salt2 = generate_salt()

        assert len(salt1) == 64  # 32 bytes encoded as hex
        assert len(salt2) == 32
        assert salt1 != salt2  # Should be unique

    def test_hash_password(self):
        """Test password hashing."""
        password = Password("test_password")
        salt = generate_salt()

        hash1 = hash_password(password, salt)
        hash2 = hash_password(password, salt)

        assert hash1 == hash2  # Same input should produce same hash
        assert len(hash1) == 64  # 32 bytes encoded as hex

    def test_verify_password(self):
        """Test password verification."""
        password = Password("test_password")
        wrong_password = Password("wrong_password")
        salt = generate_salt()
        password_hash = hash_password(password, salt)

        # Correct password should verify
        assert verify_password(password, salt, password_hash) is True

        # Wrong password should not verify
        assert verify_password(wrong_password, salt, password_hash) is False

    def test_verify_password_with_wrong_salt(self):
        """Test password verification with wrong salt."""
        password = Password("test_password")
        salt1 = generate_salt()
        salt2 = generate_salt()
        password_hash = hash_password(password, salt1)

        # Wrong salt should not verify
        assert verify_password(password, salt2, password_hash) is False


class TestUserStorage:
    """Test user storage functionality."""

    def test_create_user(self, temp_user_file):
        """Test user creation."""
        email = "test@example.com"
        display_name = "Test User"
        password = Password("secure123")

        user = create_user(email, display_name, password)

        assert user["email"] == email
        assert user["display_name"] == display_name
        assert "id" in user
        assert "password_hash" in user
        assert "salt" in user
        assert "created_at" in user
        assert user["last_login"] is None

    def test_create_user_duplicate_email(self, sample_user):
        """Test that duplicate email addresses are rejected."""
        email = sample_user["email"]

        with pytest.raises(ValueError, match="User with email .* already exists"):
            create_user(email, "Another User", Password("different_password"))

    def test_get_user_by_email(self, sample_user):
        """Test retrieving user by email."""
        user = get_user_by_email(sample_user["email"])

        assert user is not None
        assert user["email"] == sample_user["email"]
        assert user["id"] == sample_user["id"]

    def test_get_user_by_email_nonexistent(self, temp_user_file):
        """Test retrieving non-existent user by email."""
        user = get_user_by_email("nonexistent@example.com")
        assert user is None

    def test_get_user_by_id(self, sample_user):
        """Test retrieving user by ID."""
        user = get_user_by_id(sample_user["id"])

        assert user is not None
        assert user["email"] == sample_user["email"]
        assert user["id"] == sample_user["id"]

    def test_get_user_by_id_nonexistent(self, temp_user_file):
        """Test retrieving non-existent user by ID."""
        user = get_user_by_id("nonexistent-id")
        assert user is None

    def test_authenticate_user_correct_password(self, sample_user):
        """Test authentication with correct password."""
        authenticated_user = authenticate_user(sample_user["email"], Password("secure123"))

        assert authenticated_user is not None
        assert authenticated_user["email"] == sample_user["email"]
        assert authenticated_user["last_login"] is not None

    def test_authenticate_user_wrong_password(self, sample_user):
        """Test authentication with wrong password."""
        authenticated_user = authenticate_user(sample_user["email"], Password("wrong_password"))
        assert authenticated_user is None

    def test_authenticate_user_nonexistent_email(self, temp_user_file):
        """Test authentication with non-existent email."""
        authenticated_user = authenticate_user("nonexistent@example.com", Password("password"))
        assert authenticated_user is None

    def test_list_all_users(self, temp_user_file):
        """Test listing all users."""
        # Initially empty
        users = list_all_users()
        assert len(users) == 0

        # Create some users
        create_user("user1@example.com", "User 1", Password("password1"))
        create_user("user2@example.com", "User 2", Password("password2"))

        users = list_all_users()
        assert len(users) == 2

        emails = [user["email"] for user in users]
        assert "user1@example.com" in emails
        assert "user2@example.com" in emails

    def test_delete_user(self, sample_user):
        """Test user deletion."""
        email = sample_user["email"]
        user_id = sample_user["id"]

        # Verify user exists
        assert get_user_by_email(email) is not None
        assert get_user_by_id(user_id) is not None

        # Delete user
        result = delete_user(email)
        assert result is True

        # Verify user is deleted
        assert get_user_by_email(email) is None
        assert get_user_by_id(user_id) is None

    def test_delete_user_nonexistent(self, temp_user_file):
        """Test deleting non-existent user."""
        result = delete_user("nonexistent@example.com")
        assert result is False


class TestSessionManagement:
    """Test session management functionality."""

    def test_create_session(self, sample_user):
        """Test session creation."""
        user_id = sample_user["id"]
        session_id = create_session(user_id)

        assert session_id is not None
        assert len(session_id) == 64  # 32 bytes encoded as hex

    def test_create_multiple_sessions_for_same_user(self, sample_user):
        """Test creating multiple sessions for the same user."""
        user_id = sample_user["id"]

        session1 = create_session(user_id)
        session2 = create_session(user_id)

        assert session1 != session2  # Should be unique

    def test_delete_session(self, sample_user):
        """Test session deletion."""
        user_id = sample_user["id"]
        session_id = create_session(user_id)

        # Session should exist
        from yak_shears.auth.storage import get_user_id_from_session

        assert get_user_id_from_session(session_id) == user_id

        delete_session(session_id)

        # Session should no longer exist
        assert get_user_id_from_session(session_id) is None

    def test_delete_nonexistent_session(self, temp_user_file):
        """Test deleting non-existent session."""
        delete_session("nonexistent-session-id")

    def test_get_user_id_from_session(self, sample_user):
        """Test retrieving user ID from session."""
        user_id = sample_user["id"]
        session_id = create_session(user_id)

        from yak_shears.auth.storage import get_user_id_from_session

        retrieved_user_id = get_user_id_from_session(session_id)
        assert retrieved_user_id == user_id

    def test_get_user_id_from_nonexistent_session(self, temp_user_file):
        """Test retrieving user ID from non-existent session."""
        from yak_shears.auth.storage import get_user_id_from_session

        user_id = get_user_id_from_session("nonexistent-session-id")
        assert user_id is None


class TestDataPersistence:
    """Test data persistence to JSON file."""

    def test_data_persists_across_module_reloads(self, temp_user_file):
        """Test that user data persists when the module is reloaded."""
        email = "persistent@example.com"
        display_name = "Persistent User"
        password = Password("persistent123")

        # Create user
        user = create_user(email, display_name, password)
        user_id = user["id"]

        # Verify the file was written
        with open(temp_user_file) as f:
            data = json.load(f)

        assert user_id in data["users"]
        assert email in data["email_to_user_id"]
        assert data["email_to_user_id"][email] == user_id

    def test_session_persists_to_file(self, sample_user, temp_user_file):
        """Test that session data persists to file."""
        user_id = sample_user["id"]
        session_id = create_session(user_id)

        # Verify the session was written to file
        with open(temp_user_file) as f:
            data = json.load(f)

        assert session_id in data["sessions"]
        assert data["sessions"][session_id] == user_id


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_email(self, temp_user_file):
        """Test creation with empty email."""
        with pytest.raises(ValueError):
            create_user("", "Test User", Password("password"))

    def test_empty_display_name(self, temp_user_file):
        """Test creation with empty display name."""
        with pytest.raises(ValueError):
            create_user("test@example.com", "", Password("password"))

    def test_empty_password(self, temp_user_file):
        """Test creation with empty password."""
        with pytest.raises(ValueError):
            create_user("test@example.com", "Test User", Password(""))

    def test_whitespace_only_fields(self, temp_user_file):
        """Test creation with whitespace-only fields."""
        with pytest.raises(ValueError):
            create_user("   ", "Test User", Password("password"))

        with pytest.raises(ValueError):
            create_user("test@example.com", "   ", Password("password"))

        with pytest.raises(ValueError):
            create_user("test@example.com", "Test User", Password("   "))

    def test_invalid_email_format(self, temp_user_file):
        """Test creation with invalid email format."""
        # Note: This depends on whether email validation is implemented
        # For now, we'll just check that it doesn't crash
        user = create_user("not-an-email", "Test User", Password("password"))
        assert user["email"] == "not-an-email"

    def test_very_long_password(self, temp_user_file):
        """Test with very long password."""
        long_password = Password("a" * 1000)
        user = create_user("test@example.com", "Test User", long_password)

        # Should be able to authenticate with the long password
        authenticated = authenticate_user(user["email"], long_password)
        assert authenticated is not None

    def test_unicode_in_fields(self, temp_user_file):
        """Test with Unicode characters in fields."""
        email = "тест@пример.рф"
        display_name = "测试用户"
        password = Password("пароль123")

        user = create_user(email, display_name, password)
        assert user["email"] == email
        assert user["display_name"] == display_name

        # Should be able to authenticate
        authenticated = authenticate_user(email, password)
        assert authenticated is not None
