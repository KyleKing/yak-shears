"""User storage and session management."""

import json
import secrets
from pathlib import Path

from yak_shears.auth.models import User

# In-memory user storage - would be a database in production
_users: dict[str, User] = {}
_username_to_user_id: dict[str, str] = {}
_session_store: dict[str, str] = {}  # session_id -> user_id

# Path to save user data
_USER_DATA_PATH = Path(__file__).parent.parent / ".yak-shears-users.json"


def _generate_user_id() -> str:
    """Generate a random user ID.

    Returns:
        str: A randomly generated user ID as a hex string
    """
    return secrets.token_hex(16)


def _generate_session_id() -> str:
    """Generate a random session ID.

    Returns:
        str: A randomly generated session ID as a hex string
    """
    return secrets.token_hex(32)


def _save_users() -> None:
    """Save users to disk."""
    data = {
        "users": _users,
        "username_to_user_id": _username_to_user_id,
    }
    _USER_DATA_PATH.write_text(json.dumps(data, indent=2))


def _load_users() -> None:
    """Load users from disk."""
    global _users, _username_to_user_id

    if not _USER_DATA_PATH.exists():
        return

    try:
        data = json.loads(_USER_DATA_PATH.read_text())
        _users = data.get("users", {})
        _username_to_user_id = data.get("username_to_user_id", {})
    except (OSError, json.JSONDecodeError):
        # Start fresh if file is corrupt
        _users = {}
        _username_to_user_id = {}


def create_user(username: str, display_name: str) -> User:
    """Create a new user.

    Args:
        username: The username of the new user
        display_name: The display name of the new user

    Returns:
        User: The newly created user
    """
    user_id = _generate_user_id()
    user: User = {
        "id": user_id,
        "name": username,
        "display_name": display_name,
        "credentials": [],
        "current_challenge": None,
    }
    _users[user_id] = user
    _username_to_user_id[username] = user_id
    _save_users()
    return user


def get_user_by_name(username: str) -> User | None:
    """Get a user by username.

    Args:
        username: The username to look up

    Returns:
        User | None: The user if found, None otherwise
    """
    if username not in _username_to_user_id:
        return None
    user_id = _username_to_user_id[username]
    return _users.get(user_id)


def get_user_by_id(user_id: str) -> User | None:
    """Get a user by ID.

    Args:
        user_id: The user ID to look up

    Returns:
        User | None: The user if found, None otherwise
    """
    return _users.get(user_id)


def add_credential_to_user(user_id: str, credential_entry: dict) -> None:
    """Add a credential to a user.

    Args:
        user_id: The ID of the user to add the credential to
        credential_entry: The credential to add
    """
    if user_id in _users:
        _users[user_id]["credentials"].append(credential_entry)
        _save_users()


def update_credential_sign_count(user_id: str, credential_id: str, sign_count: int) -> None:
    """Update the sign count for a credential.

    Args:
        user_id: The ID of the user
        credential_id: The ID of the credential
        sign_count: The new sign count
    """
    if user_id in _users:
        for cred in _users[user_id]["credentials"]:
            if cred["id"] == credential_id:
                cred["sign_count"] = sign_count
                _save_users()
                break


def create_session(user_id: str) -> str:
    """Create a session for a user.

    Args:
        user_id: The ID of the user to create a session for

    Returns:
        str: The session ID
    """
    session_id = _generate_session_id()
    _session_store[session_id] = user_id
    return session_id


def delete_session(session_id: str) -> None:
    """Delete a session.

    Args:
        session_id: The ID of the session to delete
    """
    _session_store.pop(session_id, None)


def get_user_id_from_session(session_id: str) -> str | None:
    """Get the user ID from a session.

    Args:
        session_id: The session ID to look up

    Returns:
        str | None: The user ID if found, None otherwise
    """
    return _session_store.get(session_id)


# Load users on module import
_load_users()
