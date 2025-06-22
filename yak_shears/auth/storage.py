"""User storage and session management.

Implemented in-memory with persistence to a local JSON file

"""

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path

from .models import HashedPassword, Password, SessionId, User
from .password import create_password_hash, verify_password

# -----------------------------------------------------------------------------
# State

_USERS: dict[str, User] = {}
_EMAIL_TO_USER_ID: dict[str, str] = {}
_SESSION_STORE: dict[str, str] = {}  # session_id -> user_id

# Path to save user data
_USER_DATA_PATH = Path(__file__).parents[1] / ".yak-shears-users.json"


def _save_users() -> None:
    """Save users to disk."""
    data = {
        "users": _USERS,
        "email_to_user_id": _EMAIL_TO_USER_ID,
    }
    _USER_DATA_PATH.write_text(json.dumps(data, indent=2))


def _load_users() -> None:
    """Load users from disk."""
    global _USERS, _EMAIL_TO_USER_ID

    if not _USER_DATA_PATH.exists():
        return

    try:
        data = json.loads(_USER_DATA_PATH.read_text())
        _USERS = data.get("users", {})
        _EMAIL_TO_USER_ID = data.get("email_to_user_id", {})
    except (OSError, json.JSONDecodeError):
        _USERS = {}
        _EMAIL_TO_USER_ID = {}


_load_users()

# -----------------------------------------------------------------------------
# User Management


def create_user(email: str, display_name: str, password: Password) -> User:
    """Create a new user with email and password.

    Args:
        email: The email address of the new user
        display_name: The display name of the new user
        password: The plain text password

    Returns:
        User: The newly created user

    Raises:
        ValueError: If the email is already taken
    """
    if email in _EMAIL_TO_USER_ID:
        raise ValueError(f"Email {email} is already taken")

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

    _USERS[user_id] = user
    _EMAIL_TO_USER_ID[email] = user_id
    _save_users()
    return user


def authenticate_user(email: str, password: Password) -> User | None:
    """Authenticate a user with email and password.

    Args:
        email: The email address to authenticate
        password: The plain text password

    Returns:
        User | None: The user if authentication successful, None otherwise
    """
    user = get_user_by_email(email)
    if not user:
        return None

    if verify_password(password, user["salt"], HashedPassword(user["password_hash"])):
        user["last_login"] = datetime.now(tz=UTC).isoformat()
        _save_users()
        return user

    return None


def get_user_by_email(email: str) -> User | None:
    """Get a user by email address.

    Args:
        email: The email address to look up

    Returns:
        User | None: The user if found, None otherwise
    """
    if email not in _EMAIL_TO_USER_ID:
        return None
    user_id = _EMAIL_TO_USER_ID[email]
    return _USERS.get(user_id)


def get_user_by_id(user_id: str) -> User | None:
    """Get a user by ID.

    Args:
        user_id: The user ID to look up

    Returns:
        User | None: The user if found, None otherwise
    """
    return _USERS.get(user_id)


def list_all_users() -> list[User]:
    """Get a list of all users.

    Returns:
        list[User]: List of all users
    """
    return list(_USERS.values())


def delete_user(email: str) -> bool:
    """Delete a user by email.

    Args:
        email: The email address of the user to delete

    Returns:
        bool: True if user was deleted, False if not found
    """
    if email not in _EMAIL_TO_USER_ID:
        return False

    user_id = _EMAIL_TO_USER_ID[email]

    del _USERS[user_id]
    del _EMAIL_TO_USER_ID[email]
    _save_users()

    sessions_to_remove = [sid for sid, uid in _SESSION_STORE.items() if uid == user_id]
    for session_id in sessions_to_remove:
        del _SESSION_STORE[session_id]

    return True

# -----------------------------------------------------------------------------
# Session Management


def create_session(user_id: str) -> SessionId:
    """Create a session for a user.

    Args:
        user_id: The ID of the user to create a session for

    Returns:
        SessionId: The session ID
    """
    session_id = SessionId(secrets.token_hex(32))
    _SESSION_STORE[session_id] = user_id
    return session_id


def delete_session(session_id: str) -> None:
    """Delete a session.

    Args:
        session_id: The ID of the session to delete
    """
    _SESSION_STORE.pop(session_id, None)


def get_user_id_from_session(session_id: str) -> str | None:
    """Get the user ID from a session.

    Args:
        session_id: The session ID to look up

    Returns:
        str | None: The user ID if found, None otherwise
    """
    return _SESSION_STORE.get(session_id)
