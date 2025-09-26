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
    get_user_id_from_session,
    list_all_users,
)

from .conftest import SAMPLE_USER_EMAIL, SAMPLE_USER_PASSWORD

SALT_LENGTH = 64
"""32 bytes encoded as hex."""


def test_generate_salt():
    """Test salt generation."""
    salt1 = generate_salt()
    salt2 = generate_salt()

    assert len(salt1) == SALT_LENGTH
    assert len(salt2) == SALT_LENGTH
    assert salt1 != salt2, "Salts are not unique"


@pytest.mark.parametrize(
    ("password", "expected"),
    [
        (Password("test_password"), True),
        (Password("wrong_password"), False),
    ],
)
def test_verify_password(password, expected):
    salt = generate_salt()
    password_hash = hash_password(Password("test_password"), salt)

    assert verify_password(password, salt, password_hash) is expected


def test_create_user(temp_user_file):
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


def test_create_user_duplicate_email(sample_user):
    """Test that duplicate email addresses are rejected."""
    with pytest.raises(ValueError, match=r"Email .+ is already taken"):
        create_user(SAMPLE_USER_EMAIL, "Another User", SAMPLE_USER_PASSWORD)


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        (SAMPLE_USER_EMAIL, True),
        ("nonexistent@example.com", False),
    ],
)
def test_get_user_by_email(email, expected, temp_user_file, sample_user):
    """Test retrieving user by email."""
    user = get_user_by_email(email)

    if expected:
        assert user is not None
        assert user["email"] == email
    else:
        assert user is None


def test_get_user_by_id(sample_user):
    """Test retrieving user by ID."""
    user = get_user_by_id(sample_user["id"])

    assert user is not None
    assert user["email"] == SAMPLE_USER_EMAIL
    assert user["id"] == sample_user["id"]


def test_get_user_by_id_nonexistent(sample_user):
    """Test retrieving non-existent user by ID."""
    user = get_user_by_id("nonexistent-id")
    assert user is None


@pytest.mark.parametrize(
    ("email", "password", "expected"),
    [
        (SAMPLE_USER_EMAIL, SAMPLE_USER_PASSWORD, True),
        (SAMPLE_USER_EMAIL, Password("wrong_password"), False),
        ("nonexistent@example.com", SAMPLE_USER_PASSWORD, False),
    ],
)
def test_authenticate_user(email, password, expected, temp_user_file, sample_user):
    """Test user authentication."""
    authenticated_user = authenticate_user(email, password)

    if expected:
        assert authenticated_user is not None
        assert authenticated_user["email"] == SAMPLE_USER_EMAIL
        assert authenticated_user["last_login"] is not None
    else:
        assert authenticated_user is None


def test_list_all_users(temp_user_file):
    """Test listing all users."""
    users = list_all_users()
    assert len(users) == 0

    create_user("user1@example.com", "User 1", Password("password1"))
    create_user("user2@example.com", "User 2", Password("password2"))

    users = list_all_users()
    assert len(users) == 2  # noqa: PLR2004

    emails = {user["email"] for user in users}
    assert "user1@example.com" in emails
    assert "user2@example.com" in emails


def test_delete_user(sample_user):
    """Test user deletion."""
    user_id = sample_user["id"]

    assert get_user_by_email(SAMPLE_USER_EMAIL) is not None
    assert get_user_by_id(user_id) is not None

    result = delete_user(SAMPLE_USER_EMAIL)
    assert result is True

    assert get_user_by_email(SAMPLE_USER_EMAIL) is None
    assert get_user_by_id(user_id) is None


def test_delete_user_nonexistent(temp_user_file):
    result = delete_user("nonexistent@example.com")
    assert result is False


def test_create_session(sample_user):
    """Test session creation."""
    user_id = sample_user["id"]
    session_id = create_session(user_id)

    assert session_id is not None
    assert len(session_id) == SALT_LENGTH


def test_delete_session(sample_user):
    """Test session deletion."""
    user_id = sample_user["id"]
    session_id = create_session(user_id)
    assert get_user_id_from_session(session_id) == user_id

    delete_session(session_id)
    assert get_user_id_from_session(session_id) is None


def test_delete_nonexistent_session(temp_user_file):
    """Test deleting non-existent session."""
    delete_session("nonexistent-session-id")


def test_get_user_id_from_session(sample_user):
    """Test retrieving user ID from session."""
    user_id = sample_user["id"]
    session_id = create_session(user_id)

    retrieved_user_id = get_user_id_from_session(session_id)
    assert retrieved_user_id == user_id


def test_get_user_id_from_nonexistent_session(temp_user_file):
    """Test retrieving user ID from non-existent session."""
    user_id = get_user_id_from_session("nonexistent-session-id")
    assert user_id is None


@pytest.mark.parametrize(
    ("email", "display_name", "password"),
    [
        ("", "Test User", Password("password")),
        ("test@example.com", "", Password("password")),
        ("test@example.com", "Test User", Password("")),
        ("    ", "Test User", Password("password")),
        ("test@example.com", "    ", Password("password")),
        ("test@example.com", "Test User", Password("    ")),
    ],
    ids=[
        "Empty Email",
        "Empty Display Name",
        "Empty Password",
        "Whitespace Email",
        "Whitespace Display Name",
        "Whitespace Password",
    ],
)
def test_field_validation(temp_user_file, email, display_name, password):
    with pytest.raises(ValueError, match=r".+ cannot be empty or whitespace-only"):
        create_user(email, display_name, password)
