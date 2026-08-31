import operator
import os

import pytest

from yak_shears._auth.models import Password
from yak_shears._auth.password import generate_salt, hash_password, verify_password
from yak_shears._auth.storage import (
    UserStore,
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


@pytest.mark.asyncio
async def test_create_user(temp_user_file):
    """Test user creation."""
    email = "test@example.com"
    display_name = "Test User"
    password = Password("secure123")

    user = await create_user(email, display_name, password)

    assert user["email"] == email
    assert user["display_name"] == display_name
    assert "id" in user
    assert "password_hash" in user
    assert "salt" in user
    assert "created_at" in user
    assert user["last_login"] is None


@pytest.mark.asyncio
async def test_create_user_duplicate_email(sample_user):
    """Test that duplicate email addresses are rejected."""
    with pytest.raises(ValueError, match=r"Email .+ is already taken"):
        await create_user(SAMPLE_USER_EMAIL, "Another User", SAMPLE_USER_PASSWORD)


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


@pytest.mark.parametrize(
    ("user_id_fn", "expected_found"),
    [
        (operator.itemgetter("id"), True),
        (lambda _: "nonexistent-id", False),
    ],
    ids=["existing_user", "nonexistent_user"],
)
def test_get_user_by_id(sample_user, user_id_fn, expected_found):
    """Test retrieving user by ID (existing and non-existent)."""
    user = get_user_by_id(user_id_fn(sample_user))

    if expected_found:
        assert user is not None
        assert user["email"] == SAMPLE_USER_EMAIL
        assert user["id"] == sample_user["id"]
    else:
        assert user is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("email", "password", "expected"),
    [
        (SAMPLE_USER_EMAIL, SAMPLE_USER_PASSWORD, True),
        (SAMPLE_USER_EMAIL, Password("wrong_password"), False),
        ("nonexistent@example.com", SAMPLE_USER_PASSWORD, False),
    ],
)
async def test_authenticate_user(email, password, expected, temp_user_file, sample_user):
    """Test user authentication."""
    authenticated_user = await authenticate_user(email, password)

    if expected:
        assert authenticated_user is not None
        assert authenticated_user["email"] == SAMPLE_USER_EMAIL
        assert authenticated_user["last_login"] is not None
    else:
        assert authenticated_user is None


@pytest.mark.asyncio
async def test_list_all_users(temp_user_file):
    """Test listing all users."""
    users = list_all_users()
    assert len(users) == 0

    await create_user("user1@example.com", "User 1", Password("password1"))
    await create_user("user2@example.com", "User 2", Password("password2"))

    users = list_all_users()
    assert len(users) == 2  # noqa: PLR2004

    emails = {user["email"] for user in users}
    assert "user1@example.com" in emails
    assert "user2@example.com" in emails


@pytest.mark.asyncio
async def test_delete_user(sample_user):
    """Test user deletion."""
    user_id = sample_user["id"]

    assert get_user_by_email(SAMPLE_USER_EMAIL) is not None
    assert get_user_by_id(user_id) is not None

    result = await delete_user(SAMPLE_USER_EMAIL)
    assert result is True

    assert get_user_by_email(SAMPLE_USER_EMAIL) is None
    assert get_user_by_id(user_id) is None


@pytest.mark.asyncio
async def test_delete_user_nonexistent(temp_user_file):
    result = await delete_user("nonexistent@example.com")
    assert result is False


def test_create_session(sample_user):
    """Test session creation."""
    user_id = sample_user["id"]
    session_id = create_session(user_id)

    assert session_id is not None
    assert get_user_id_from_session(session_id) == user_id


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


@pytest.mark.asyncio
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
async def test_field_validation(temp_user_file, email, display_name, password):
    with pytest.raises(ValueError, match=r".+ cannot be empty or whitespace-only"):
        await create_user(email, display_name, password)


class TestUserStore:
    """Tests for the UserStore class directly."""

    @pytest.fixture
    def store(self, tmp_path) -> UserStore:
        return UserStore(tmp_path / "users.json")

    @pytest.mark.asyncio
    async def test_create_and_get_user(self, store):
        user = await store.create_user("test@test.com", "Test", Password("pass123"))
        assert store.get_user_by_email("test@test.com") == user
        assert store.get_user_by_id(user["id"]) == user

    @pytest.mark.asyncio
    async def test_persistence(self, tmp_path):
        path = tmp_path / "users.json"
        store1 = UserStore(path)
        await store1.create_user("test@test.com", "Test", Password("pass123"))

        store2 = UserStore.load_sync(path)
        assert store2.get_user_by_email("test@test.com") is not None

    @pytest.mark.asyncio
    async def test_session_management(self, store):
        user = await store.create_user("test@test.com", "Test", Password("pass123"))
        session_id = store.create_session(user["id"])
        assert store.get_user_id_from_session(session_id) == user["id"]

        store.delete_session(session_id)
        assert store.get_user_id_from_session(session_id) is None

    @pytest.mark.asyncio
    async def test_session_drops_a_user_the_cli_deleted(self, tmp_path):
        path = tmp_path / "users.json"
        store = UserStore(path)
        user = await store.create_user("test@test.com", "Test", Password("pass123"))
        session_id = store.create_session(user["id"])

        other = UserStore.load_sync(path)
        assert await other.delete_user("test@test.com")
        stat = path.stat()
        os.utime(path, (stat.st_atime, stat.st_mtime + 1))

        assert store.get_user_id_from_session(session_id) is None

    @pytest.mark.asyncio
    async def test_half_written_file_keeps_the_loaded_users(self, tmp_path):
        path = tmp_path / "users.json"
        store = UserStore(path)
        user = await store.create_user("test@test.com", "Test", Password("pass123"))
        session_id = store.create_session(user["id"])

        path.write_text('{"users": {"tru')
        stat = path.stat()
        os.utime(path, (stat.st_atime, stat.st_mtime + 1))

        assert store.get_user_id_from_session(session_id) == user["id"]

    def test_clear(self, store):
        store.create_session("user123")
        store.clear()
        assert store.list_all_users() == []
        assert store.get_user_id_from_session("any") is None

    def test_load_sync_corrupted_json(self, tmp_path):
        """Test that load_sync handles corrupted JSON gracefully."""
        path = tmp_path / "corrupted.json"
        path.write_text("{invalid json content")

        store = UserStore.load_sync(path)
        # Should create empty store instead of crashing
        assert store.list_all_users() == []

    def test_load_sync_missing_file(self, tmp_path):
        """Test that load_sync handles missing file gracefully."""
        path = tmp_path / "nonexistent.json"

        store = UserStore.load_sync(path)
        # Should create empty store
        assert store.list_all_users() == []

    @pytest.mark.asyncio
    async def test_delete_user_with_active_sessions(self, tmp_path):
        """Test that deleting a user also deletes their active sessions."""
        path = tmp_path / "users.json"
        store = UserStore(path)

        # Create user and session
        user = await store.create_user("test@example.com", "Test", Password("pass123"))
        user_id = user["id"]
        session_id = store.create_session(user_id)

        # Verify session exists
        assert store.get_user_id_from_session(session_id) == user_id

        # Delete user
        result = await store.delete_user("test@example.com")
        assert result is True

        # Verify session is also deleted
        assert store.get_user_id_from_session(session_id) is None
