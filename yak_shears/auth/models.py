"""Authentication models for Yak Shears."""

from typing import NewType, TypedDict

Password = NewType("Password", str)
HashedPassword = NewType("HashedPassword", str)
SessionId = NewType("SessionId", str)


class User(TypedDict):
    """User model for password authentication."""

    id: str
    email: str
    display_name: str
    password_hash: HashedPassword
    salt: str
    created_at: str
    last_login: str | None
