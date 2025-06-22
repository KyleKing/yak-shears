"""Pytest configuration."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


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
