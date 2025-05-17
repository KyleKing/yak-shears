"""Authentication data models."""

from typing import Any, TypedDict


class User(TypedDict):
    """User data structure."""

    id: str
    name: str
    display_name: str
    credentials: list[dict[str, Any]]
    current_challenge: str | None


class CredentialEntry(TypedDict):
    """Credential data structure."""

    id: str
    public_key: str
    sign_count: int
    transports: list[str] | None
