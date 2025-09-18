"""Playwright integration tests for the server."""

import subprocess
import time
from contextlib import contextmanager

import pytest


@contextmanager
def server_lifecycle():
    """Context manager to start and stop the server."""
    # Start the server in the background
    process = subprocess.Popen(
        ["uv", "run", "serve", "--no-auth", "--reload", "--host", "localhost", "--port", "8080"],
        cwd="/Users/kyleking/Developer/kyleking/yak-shears-py",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start
    time.sleep(2)

    try:
        yield "http://localhost:8080"
    finally:
        # Clean up server process
        process.terminate()
        process.wait()


@pytest.mark.playwright
def test_server_starts_and_serves_homepage(page):
    """Test that the server starts and serves the homepage."""
    with server_lifecycle() as base_url:
        page.goto(base_url)
        assert page.title() == "Notes in ./Sync/yak-shears"


@pytest.mark.playwright
def test_login_page_loads(page):
    """Test that the login page loads correctly."""
    with server_lifecycle() as base_url:
        page.goto(f"{base_url}/auth/login")
        assert "Login" in page.content()


@pytest.mark.playwright
def test_files_page_loads(page):
    """Test that the files page loads correctly."""
    with server_lifecycle() as base_url:
        page.goto(f"{base_url}/files")
        assert "Notes" in page.content()
