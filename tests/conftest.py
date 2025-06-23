"""Pytest configuration."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from yak_shears.auth import routes
from yak_shears.auth.models import HashedPassword, User


@pytest.fixture
def temp_user_file():
    """Create a temporary user file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as _f:
        temp_path = Path(_f.name)
        _f.write('{"users": {}, "email_to_user_id": {}, "sessions": {}}')

    with (
        patch("yak_shears.auth.storage._USER_DATA_PATH", temp_path),
        patch("yak_shears.auth.storage._USERS", {}),
        patch("yak_shears.auth.storage._EMAIL_TO_USER_ID", {}),
        patch("yak_shears.auth.storage._SESSION_STORE", {}),
    ):
        yield temp_path

    temp_path.unlink(missing_ok=True)


@pytest.fixture
def mock_user_session():
    """Fixture to patch `get_user_from_session` and provide a mock user."""
    with patch.object(routes, "get_user_from_session") as mock_get_user:
        mock_user = User(
            {
                "id": "test_user_id",
                "email": "test@web.site",
                "display_name": "Test User",
                "password_hash": HashedPassword("123"),
                "salt": "abc",
                "created_at": "2025-05-30T19:52:12.943795+00:00",
                "last_login": None,
            }
        )
        mock_get_user.return_value = mock_user
        yield mock_get_user
