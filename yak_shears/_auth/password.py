"""Password management utilities for authentication."""

import hashlib
import secrets

from .models import HashedPassword, Password


def generate_salt() -> str:
    """Generate a random salt for password hashing.

    Returns:
        str: A randomly generated salt as a hex string
    """
    return secrets.token_hex(32)


def hash_password(password: Password, salt: str) -> HashedPassword:
    """Hash a password with a salt using PBKDF2.

    Args:
        password: The plain text password to hash
        salt: The salt to use for hashing

    Returns:
        str: The hashed password as a hex string
    """
    password_bytes = password.encode("utf-8")
    salt_bytes = bytes.fromhex(salt)

    # Using PBKDF2 with SHA256, 100000 iterations (recommended by OWASP)
    hashed = hashlib.pbkdf2_hmac("sha256", password_bytes, salt_bytes, 100000)
    return HashedPassword(hashed.hex())


def verify_password(password: Password, salt: str, hashed_password: HashedPassword) -> bool:
    """Verify a password against a stored hash.

    Args:
        password: The plain text password to verify
        salt: The salt used for the original hash
        hashed_password: The stored password hash

    Returns:
        bool: True if the password is correct, False otherwise
    """
    computed_hash = hash_password(password, salt)
    return secrets.compare_digest(computed_hash, hashed_password)


def create_password_hash(password: Password) -> tuple[str, HashedPassword]:
    """Create a salt and hash for a new password.

    Args:
        password: The plain text password

    Returns:
        Tuple[str, HashedPassword]: A tuple of (salt, hash) both as hex strings
    """
    salt = generate_salt()
    password_hash = hash_password(password, salt)
    return salt, password_hash
