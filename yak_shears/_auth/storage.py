"""User storage and session management.

Provides a UserStore class for managing users and sessions with JSON persistence.
A module-level default store is provided for backward compatibility.
"""

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path as SyncPath
from typing import Self

from anyio import Path

from .models import HashedPassword, Password, SessionId, User
from .password import create_password_hash, hash_password, verify_password

DEFAULT_USER_DATA_PATH = SyncPath(__file__).parents[1] / ".yak-shears-users.json"

_DUMMY_SALT = secrets.token_hex(32)
_DUMMY_HASH = hash_password(Password(secrets.token_hex(16)), _DUMMY_SALT)


class UserStore:
    """Manages user accounts and sessions with JSON file persistence."""

    def __init__(self, data_path: SyncPath | None = None) -> None:
        self._data_path = Path(data_path) if data_path else Path(DEFAULT_USER_DATA_PATH)
        self._users: dict[str, User] = {}
        self._email_to_user_id: dict[str, str] = {}
        self._session_store: dict[str, str] = {}

    @classmethod
    def load_sync(cls, data_path: SyncPath | None = None) -> Self:
        """Load store synchronously (for module initialization).

        Returns:
            Initialized UserStore instance with data loaded from disk if available.
        """
        store = cls(data_path)
        sync_path = SyncPath(store._data_path)
        if sync_path.exists():
            try:
                data = json.loads(sync_path.read_text(encoding="utf-8"))
                store._users = data.get("users", {})
                store._email_to_user_id = data.get("email_to_user_id", {})
            except (OSError, json.JSONDecodeError):
                pass
        return store

    async def load(self) -> None:
        """Load users from disk."""
        if not await self._data_path.exists():
            return

        try:
            data = json.loads(await self._data_path.read_text())
            self._users = data.get("users", {})
            self._email_to_user_id = data.get("email_to_user_id", {})
        except (OSError, json.JSONDecodeError):
            self._users = {}
            self._email_to_user_id = {}

    async def _save(self) -> None:
        """Save users to disk."""
        data = {
            "users": self._users,
            "email_to_user_id": self._email_to_user_id,
        }
        await self._data_path.write_text(json.dumps(data, indent=2))

    # -------------------------------------------------------------------------
    # User Management

    async def create_user(self, email: str, display_name: str, password: Password) -> User:
        """Create a new user with email and password.

        Returns:
            Newly created User dict.

        Raises:
            ValueError: If email, display_name, or password is empty/whitespace,
                       or if email is already taken.
        """
        if not email.strip():
            raise ValueError("Email cannot be empty or whitespace-only")

        if not display_name.strip():
            raise ValueError("Display name cannot be empty or whitespace-only")

        if not password.strip():
            raise ValueError("Password cannot be empty or whitespace-only")

        if email in self._email_to_user_id:
            msg = f"Email {email} is already taken"
            raise ValueError(msg)

        user_id = secrets.token_hex(16)
        salt, password_hash = create_password_hash(password)
        now = datetime.now(tz=UTC).isoformat()

        user: User = {
            "id": user_id,
            "email": email,
            "display_name": display_name,
            "password_hash": password_hash,
            "salt": salt,
            "created_at": now,
            "last_login": None,
        }

        self._users[user_id] = user
        self._email_to_user_id[email] = user_id
        await self._save()
        return user

    async def authenticate_user(self, email: str, password: Password) -> User | None:
        """Authenticate a user with email and password.

        Returns:
            User dict if authentication successful, None otherwise.
        """
        user = self.get_user_by_email(email)
        if not user:
            verify_password(password, _DUMMY_SALT, _DUMMY_HASH)
            return None

        if verify_password(password, user["salt"], HashedPassword(user["password_hash"])):
            user["last_login"] = datetime.now(tz=UTC).isoformat()
            await self._save()
            return user

        return None

    def get_user_by_email(self, email: str) -> User | None:
        """Get a user by email address.

        Returns:
            User dict if found, None otherwise.
        """
        if email not in self._email_to_user_id:
            return None
        user_id = self._email_to_user_id[email]
        return self._users.get(user_id)

    def get_user_by_id(self, user_id: str) -> User | None:
        """Get a user by ID.

        Returns:
            User dict if found, None otherwise.
        """
        return self._users.get(user_id)

    def list_all_users(self) -> list[User]:
        """Get a list of all users.

        Returns:
            List of all User dicts.
        """
        return list(self._users.values())

    async def delete_user(self, email: str) -> bool:
        """Delete a user by email.

        Returns:
            True if user was deleted, False if user not found.
        """
        if email not in self._email_to_user_id:
            return False

        user_id = self._email_to_user_id[email]

        del self._users[user_id]
        del self._email_to_user_id[email]
        await self._save()

        sessions_to_remove = [sid for sid, uid in self._session_store.items() if uid == user_id]
        for session_id in sessions_to_remove:
            del self._session_store[session_id]

        return True

    # -------------------------------------------------------------------------
    # Session Management

    def create_session(self, user_id: str) -> SessionId:
        """Create a session for a user.

        Returns:
            New session ID.
        """
        session_id = SessionId(secrets.token_hex(32))
        self._session_store[session_id] = user_id
        return session_id

    def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        self._session_store.pop(session_id, None)

    def get_user_id_from_session(self, session_id: str) -> str | None:
        """Get the user ID from a session.

        Returns:
            User ID if session exists, None otherwise.
        """
        return self._session_store.get(session_id)

    # -------------------------------------------------------------------------
    # Testing helpers

    def clear(self) -> None:
        """Clear all users and sessions (for testing)."""
        self._users.clear()
        self._email_to_user_id.clear()
        self._session_store.clear()


# -----------------------------------------------------------------------------
# Default store instance (for backward compatibility)

_default_store = UserStore.load_sync()


# Module-level functions that delegate to default store
async def create_user(email: str, display_name: str, password: Password) -> User:
    """Create a new user with email and password.

    Returns:
        Newly created User dict.
    """
    return await _default_store.create_user(email, display_name, password)


async def authenticate_user(email: str, password: Password) -> User | None:
    """Authenticate a user with email and password.

    Returns:
        User dict if authentication successful, None otherwise.
    """
    return await _default_store.authenticate_user(email, password)


def get_user_by_email(email: str) -> User | None:
    """Get a user by email address.

    Returns:
        User dict if found, None otherwise.
    """
    return _default_store.get_user_by_email(email)


def get_user_by_id(user_id: str) -> User | None:
    """Get a user by ID.

    Returns:
        User dict if found, None otherwise.
    """
    return _default_store.get_user_by_id(user_id)


def list_all_users() -> list[User]:
    """Get a list of all users.

    Returns:
        List of all User dicts.
    """
    return _default_store.list_all_users()


async def delete_user(email: str) -> bool:
    """Delete a user by email.

    Returns:
        True if user was deleted, False if user not found.
    """
    return await _default_store.delete_user(email)


def create_session(user_id: str) -> SessionId:
    """Create a session for a user.

    Returns:
        New session ID.
    """
    return _default_store.create_session(user_id)


def delete_session(session_id: str) -> None:
    """Delete a session."""
    _default_store.delete_session(session_id)


def get_user_id_from_session(session_id: str) -> str | None:
    """Get the user ID from a session.

    Returns:
        User ID if session exists, None otherwise.
    """
    return _default_store.get_user_id_from_session(session_id)


def _get_default_store() -> UserStore:
    """Get the default store instance (for testing).

    Returns:
        The module-level default UserStore instance.
    """
    return _default_store


def _set_default_store(store: UserStore) -> None:
    """Set the default store instance (for testing)."""
    global _default_store  # noqa: PLW0603
    _default_store = store
