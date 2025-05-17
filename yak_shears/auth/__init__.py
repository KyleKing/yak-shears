"""Authentication module for Yak Shears."""

from yak_shears.auth.middleware import AuthMiddleware
from yak_shears.auth.models import CredentialEntry, User
from yak_shears.auth.routes import auth_routes

# For backward compatibility with existing code
# Internal implementation details that shouldn't be directly used
from yak_shears.auth.storage import (
    _load_users,
    add_credential_to_user,
    create_session,
    create_user,
    delete_session,
    get_user_by_id,
    get_user_by_name,
    update_credential_sign_count,
)
from yak_shears.auth.webauthn import (
    generate_auth_options_for_user,
    get_user_from_session,
    verify_authentication,
)


def initialize() -> None:
    """Initialize the auth system."""
    _load_users()


__all__ = [
    "AuthMiddleware",
    "CredentialEntry",
    "User",
    "add_credential_to_user",
    "auth_routes",
    "create_session",
    "create_user",
    "delete_session",
    "generate_auth_options_for_user",
    "get_user_by_id",
    "get_user_by_name",
    "get_user_from_session",
    "initialize",
    "update_credential_sign_count",
    "verify_authentication",
]
